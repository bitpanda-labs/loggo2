## Contributing

Issues, feature requests and code contributions are welcomed.

`loggo` adheres to semantic versioning, ideally via the `bump2version` utility. Install it with pip:

```bash
pip install bump2version
```

Whenever you need to bump version, in the project root directory do:

```bash
bump2version (major | minor | patch)
git push <remote> <branch> --follow-tags 
```

## Limitations

`loggo` uses Python's standard library (`logging`) to generate logs. There are some gotchas when using it: for instance, in terms of the extra data that can be passed in, key names for this extra data cannot clash with some internal names used within the `logging` module (`message`, `args`, etc.). To get around this, you'll get a warning that your data contains a bad key name, and it will be changed (i.e. from `message` to `protected_message`).
