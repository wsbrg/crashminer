import torch
import transformers
from pathlib import Path
from fsdict import fsdict
from tqdm import tqdm


# from https://github.com/salesforce/CodeT5/blob/d929a71f98ba58491948889d554f8276c92f98ae/CodeT5/models.py#LL123C1-L181C24
class DefectModel(transformers.PreTrainedModel):
    def __init__(self, encoder, config, tokenizer, class_weights=None):
        super(DefectModel, self).__init__(config)
        self.encoder = encoder
        self.config = config
        self.tokenizer: transformers.PreTrainedTokenizer = tokenizer
        self.classifier = torch.nn.Linear(config.hidden_size, 2)
        self.loss_fct = torch.nn.CrossEntropyLoss(weight=class_weights)

        self.line_seperator_ids = self.tokenizer.convert_tokens_to_ids(
            [token for token in self.tokenizer.vocab if "Ċ" in token]
        )

    def get_t5_vec(self, source_ids, attention_mask=None):
        if attention_mask is None:
            attention_mask = source_ids.ne(self.tokenizer.pad_token_id)
        outputs = self.encoder(
            input_ids=source_ids,
            attention_mask=attention_mask,
            labels=source_ids,
            decoder_attention_mask=attention_mask,
            output_hidden_states=True,
        )
        hidden_states = outputs["decoder_hidden_states"][-1]
        eos_mask = source_ids.eq(self.config.eos_token_id)

        if len(torch.unique(eos_mask.sum(1))) > 1:
            raise ValueError("All examples must have the same number of <eos> tokens.")
        vec = hidden_states[eos_mask, :].view(
            hidden_states.size(0), -1, hidden_states.size(-1)
        )[:, -1, :]

        return vec

    def forward(self, input_ids: torch.Tensor, attention_mask=None, labels=None):
        input_ids = input_ids.view(-1, self.tokenizer.model_max_length)
        vec = self.get_t5_vec(input_ids, attention_mask=attention_mask)

        logits = self.classifier(vec)
        prob = torch.nn.functional.softmax(logits, dim=-1)

        if labels is not None:
            loss = torch.nn.functional.cross_entropy(logits, labels)
            return loss, prob
        else:
            return prob


@torch.no_grad()
def codet5p_score(input_path, tokenizer, model, device):
    with torch.cuda.amp.autocast():  # for fp16
        input_ids = tokenizer.encode(
            open(str(input_path), "r").read(),
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        pred = model(input_ids.to(device)).cpu().tolist()

    return pred[0][1]


def codet5p_metric(database):
    model_name = "Salesforce/codet5p-220m"
    checkpoint_path = "assets/model_normalized.bin"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    tokenizer = transformers.AutoTokenizer.from_pretrained(model_name)
    config_kwargs = {
        "vocab_size": len(tokenizer),
        "scale_attn_by_inverse_layer_idx": True,
        "reorder_and_upcast_attn": True,
    }
    config = transformers.AutoConfig.from_pretrained(model_name, **config_kwargs)
    model = transformers.T5ForConditionalGeneration.from_pretrained(
        model_name, config=config
    )
    model = DefectModel(model, config, tokenizer, None)
    model.load_state_dict(
        torch.load(checkpoint_path, map_location=torch.device("cpu")), strict=False
    )

    model.eval()
    model.to(device)

    for function in tqdm(database.values(), total=len(database)):
        meta = function["meta"]
        source_path = function.abspath / "source"
        score = codet5p_score(source_path, tokenizer, model, device)

        if not "metrics" in meta:
            meta["metrics"] = {}
        metrics = meta["metrics"]

        metrics["codet5p"] = score
        meta["metrics"] = metrics
        function["meta"] = meta
