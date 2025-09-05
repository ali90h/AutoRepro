# Deletion Policy

Code is deleted if it is: not called, duplicated, or can be replaced by an existing function.
Any necessary deletion must be subject to a ripgrep text search that proves non-use:
`rg -n "<SymbolName>" -S || echo "no refs"`
Any deletion accompanied by a link to the result of the vulture + rg search.
No unauthorized deletion is permitted.
