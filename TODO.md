# TODO

- Support inline comments (end-of-line `# ...`) — currently `COMMENT: /#[^\n]*\n/` consumes the trailing newline, breaking statements that expect a `_NEWLINE` terminator
- Make `@case` weight optional with a default of 1 (grammar + transformer + move `missing_weight` fixture from invalid to valid)
