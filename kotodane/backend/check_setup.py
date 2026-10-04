import sys

from fugashi import Tagger
from jamdict import Jamdict

# Print Japanese text reliably in Windows terminals using legacy encodings.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


sentence = "私は日本語を勉強しています"
tagger = Tagger()
print("Tokens:")
for token in tagger(sentence):
    print(f"{token.surface}\t{token.feature}")

print("\nJamdict lookup for 食べる:")
result = Jamdict().lookup("食べる")
for entry in result.entries:
    print(entry)
if not result.entries:
    print("No dictionary entries found.")
