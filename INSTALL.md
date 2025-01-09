# Install
* Install miniconda
  https://docs.anaconda.com/miniconda/install/
* clone repo
* cd into repo
* conda env create -f environment.yaml
* add `conda activate paula` to your shell environment

# Develop
* vscode `settings.json`
```
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.ruffEnabled": true,
    "python.linting.flake8Path": "flake8",
    "python.linting.ruffPath": "ruff",
    "python.linting.lintOnSave": true,
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "ms-python.black-formatter",
    "[python]": {
        "editor.formatOnSave": true
    },
    "python.formatting.provider": "black",
```

# Remove
* `conda env remove -n paula` 
