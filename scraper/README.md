# Scrape information from the OSS-Fuzz bugtracker

## Run
To collect meta information about crashes as well as their respective testcases, run:
```
./build.sh
./run.sh
```
Once this finished you can find the meta information in `data/projects.json` and the testcases in `data/testcases`. Each file in the testcase directory is named through the crash identification number of the crash that it corresponds to. The crash id aligns with the id in the OSS-Fuzz [bugtracker](https://issues.oss-fuzz.com/issues).

## Note
The code was used with the 2023 version of the OSS-Fuzz [bugtracker](https://issues.oss-fuzz.com/issues) website.
