# TODO

- Support inline comments (end-of-line `# ...`) — currently `COMMENT: /#[^\n]*\n/` consumes the trailing newline, breaking statements that expect a `_NEWLINE` terminator
