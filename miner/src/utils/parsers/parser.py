import os
from tree_sitter import Language, Parser
from utils.utils import hashdict
from config import PREPARSE_DEPTH

try:
    C_LANGUAGE = Language("utils/parsers/build/languages.so", "c")
    CPP_LANGUAGE = Language("utils/parsers/build/languages.so", "cpp")

    # For c-style functions
    QUERY_FUNCS_C = C_LANGUAGE.query(
        """
    (function_definition
      [
        (function_declarator
          (identifier)
        )
        (pointer_declarator
          (function_declarator
            (identifier)
          )
        )
      ]
    ) @function
    """
    )
    QUERY_FUNC_NAME_C = C_LANGUAGE.query(
        """
    (function_definition
      [
        (function_declarator
          (identifier) @name
        )
        (pointer_declarator
          (function_declarator
            (identifier) @name
          )
        )
      ]
    )
    """
    )

    # For cpp-style functions
    QUERY_FUNCS_CPP = CPP_LANGUAGE.query(
        """
    (function_definition 
      [
        (function_declarator (identifier))
        (function_declarator (qualified_identifier))
        (function_declarator (operator_name))
        (function_declarator (field_identifier)) (pointer_declarator (function_declarator (identifier)))
        (pointer_declarator (function_declarator (qualified_identifier)))
        (pointer_declarator (function_declarator (operator_name)))
        (pointer_declarator (function_declarator (field_identifier)))
        (reference_declarator (function_declarator (identifier)))
        (reference_declarator (function_declarator (qualified_identifier)))
        (reference_declarator (function_declarator (operator_name)))
        (reference_declarator (function_declarator (field_identifier)))
      ]
    ) @function
    """
    )

    QUERY_FUNC_IDENTIFIER_SUBTREE = CPP_LANGUAGE.query(
        """
    (function_definition 
      [
        (function_declarator (identifier) @subtree)
        (function_declarator (qualified_identifier) @subtree)
        (function_declarator (operator_name) @subtree)
        (function_declarator (field_identifier) @subtree)
        (pointer_declarator (function_declarator (identifier) @subtree))
        (pointer_declarator (function_declarator (qualified_identifier) @subtree))
        (pointer_declarator (function_declarator (operator_name) @subtree))
        (pointer_declarator (function_declarator (field_identifier) @subtree))
        (reference_declarator (function_declarator (identifier) @subtree))
        (reference_declarator (function_declarator (qualified_identifier) @subtree))
        (reference_declarator (function_declarator (operator_name) @subtree))
        (reference_declarator (function_declarator (field_identifier) @subtree))
      ]
    )
    """
    )
    QUERY_FUNC_NAME_CPP = CPP_LANGUAGE.query(
        """
    [
      (identifier) @name
      (field_identifier) @name
      (operator_name) @name
    ]
    """
    )
except OSError:
    print("\nWARNING! Parsers not available.\n")


def print_tree(node, depth=0):
    print("%s%s" % (" " * depth * 2, node))

    for node in node.children:
        print_tree(node, depth + 1)


def get_name(function, is_cpp=False):
    if is_cpp:
        subtrees = QUERY_FUNC_IDENTIFIER_SUBTREE.captures(function)
        if len(subtrees) != 1:
            # print("WARNING! Invalid number of identifier subtrees.", function)
            return ""
        subtree, _ = subtrees[0]
        name_matches = QUERY_FUNC_NAME_CPP.captures(subtree)
    else:
        name_matches = QUERY_FUNC_NAME_C.captures(function)
    if len(name_matches) != 1:
        # print("WARNING! Invalid number of name matches for function", function)
        return ""
    return name_matches[0][0].text.decode("ascii")


def parse_bytes(data, lang):
    # Create parser
    parser = Parser()

    # Set language
    if lang == "c":
        parser.set_language(C_LANGUAGE)
    elif lang == "cpp":
        parser.set_language(CPP_LANGUAGE)

    # Parse data
    tree = parser.parse(data)

    return tree


def parse_file(fpath):
    # We can only parse C/C++ files
    _, ext = os.path.splitext(fpath)
    lang = ext.lower().replace(".", "")
    assert lang == "c" or lang == "cpp"

    # Read and parse source file
    with open(fpath, "rb") as f:
        data = f.read()
    return parse_bytes(data, lang), lang


def treesitter_iter_functions_tree(tree, lang):
    # Query functions
    if lang == "c":
        functions = QUERY_FUNCS_C.captures(tree.root_node)
    elif lang == "cpp":
        functions = QUERY_FUNCS_CPP.captures(tree.root_node)

    for function, _ in functions:
        name = get_name(function, is_cpp=lang == "cpp")
        start = function.start_point[0]
        end = function.end_point[0] + 1
        start_col = function.start_point[1]
        end_col = function.end_point[1]
        yield hashdict(
            name=name, start=start, end=end, start_col=start_col, end_col=end_col
        )


def treesitter_iter_functions_bytes(data, lang):
    # Parse data and create parse tree
    tree = parse_bytes(data, lang)
    yield from treesitter_iter_functions_tree(tree, lang)


def treesitter_iter_functions_file(fpath):
    # Read and parse file
    tree, lang = parse_file(fpath)
    functions = treesitter_iter_functions_tree(tree, lang)
    for function in functions:
        function["fpath"] = fpath
        yield function


def is_function(data, lang):
    functions = list(treesitter_iter_functions_bytes(data, lang))
    return len(functions) == 1


def traverse_inorder(data, root_node):
    yield data[root_node["start"] : root_node["end"]]
    for child in root_node["children"]:
        yield from traverse_inorder(data, child)


def create_block_tree(data, max_depth):
    """

    Read the data and return a tree of blocks { ... }.
    """
    data = data.decode("utf-8", errors="ignore")
    root_node = hashdict(start=0, end=len(data), children=[], parent=None)
    current_node = root_node
    in_double_quotes = False
    in_single_quotes = False
    escape = False
    depth = 0
    for idx in range(0, len(data)):
        if escape:
            escape = False
            continue
        if data[idx] == "\\":
            # Escape
            escape = True
            continue
        if not in_single_quotes and data[idx] == '"':
            # Double quotes
            in_double_quotes ^= True
            continue
        if not in_double_quotes and data[idx] == "'":
            # Single quotes
            in_single_quotes ^= True
            continue

        if in_double_quotes or in_single_quotes:
            continue

        # Block start
        if data[idx] == "{":
            if depth < max_depth:
                node = hashdict(start=idx, end=None, children=[], parent=current_node)
                current_node["children"].append(node)
                current_node = node
            depth += 1
            continue
        # Block end
        if data[idx] == "}":
            depth -= 1
            if depth < max_depth:
                current_node["end"] = idx + 1
                current_node = current_node["parent"]
    return root_node


def expand_backwards(data, blocks):
    """

    Set the start of the block backwards right after a ";", ":", or "}"
    """
    adjusted_blocks = []
    string = data.decode("utf-8", errors="ignore")
    for block_start, block_end in blocks:
        # Trivial case block_start is beginning of data
        if block_start == 0:
            adjusted_blocks.append((block_start, block_end))
            continue

        # block_start index is greater than beginning of data
        for idx in range(block_start - 1, -1, -1):
            char = string[idx]
            if char == ";" or char == "}":
                break
            if char == ":" and idx - 1 >= 0:
                if string[idx - 1] != ":" and string[idx + 1] != ":":
                    # e. g. public: and private:
                    break
        if idx == 0:
            block_start = 0
        else:
            block_start = idx + 1
        adjusted_blocks.append((block_start, block_end))
    return adjusted_blocks


def node_iter_functions_bytes(data, node, lang):
    for child in node["children"]:
        yield from node_iter_functions_bytes(data, child, lang)
    adjusted_block_start, block_end = expand_backwards(
        data, [(node["start"], node["end"])]
    )[0]
    line_offset = max(
        0,
        len(data.decode("utf-8", errors="ignore")[:adjusted_block_start].split("\n"))
        - 1,
    )
    functions = treesitter_iter_functions_bytes(
        data.decode("utf-8", errors="ignore")[adjusted_block_start:block_end].encode(
            "utf-8"
        ),
        lang,
    )
    for function in functions:
        function["start"] += line_offset
        function["end"] += line_offset
        yield function


def iter_functions_bytes(data, lang):
    """

    Since huge files constitute a problem for tree_sitter, we
    break the file into pieces until each piece can either not be broken
    down any further or consists of a single function definition only.
    """
    root_node = create_block_tree(data, PREPARSE_DEPTH)
    functions = {}
    # Remove duplicates and use shorter function variant for ambigious
    # functions
    for function in node_iter_functions_bytes(data, root_node, lang):
        if function["end"] not in functions:
            functions[function["end"]] = function
        elif function["start"] > functions[function["end"]]["start"]:
            functions[function["end"]] = function
    return list(functions.values())


def iter_functions_file(fpath):
    """

    Since huge files constitute a problem for tree_sitter, we
    break the file into pieces until each piece can either not be broken
    down any further or consists of a single function definition only.
    """
    _, ext = os.path.splitext(fpath)
    lang = ext.lower().replace(".", "")
    assert lang == "c" or lang == "cpp"

    with open(fpath, "rb") as f:
        data = f.read()
    return iter_functions_bytes(data, lang)


def test_main():
    ## Operator-
    # fpath = "/tmp/test/test_difference_type_operator.cpp"
    # print(fpath)
    # functions = iter_functions_file(fpath)
    # for function in functions:
    #    print(function)
    #    pass

    # Add to vector
    fpath = "/tmp/test/test_add_to_vector.cpp"
    print(fpath)
    functions = iter_functions_file(fpath)
    for function in functions:
        print(function)
        pass


if __name__ == "__main__":
    test_main()
