# routelit

[![Release](https://img.shields.io/github/v/release/routelit/routelit)](https://img.shields.io/github/v/release/routelit/routelit)
[![Build status](https://img.shields.io/github/actions/workflow/status/routelit/routelit/main.yml?branch=main)](https://github.com/routelit/routelit/actions/workflows/main.yml?query=branch%3Amain)
[![Commit activity](https://img.shields.io/github/commit-activity/m/routelit/routelit)](https://img.shields.io/github/commit-activity/m/routelit/routelit)
[![License](https://img.shields.io/github/license/routelit/routelit)](https://img.shields.io/github/license/routelit/routelit)

![Routelit](https://wsrv.nl/?url=res.cloudinary.com/rolangom/image/upload/v1747976918/routelit/routelit_c2otsv.png&w=200&h=200)

**routelit** is a Python framework for building interactive web user interfaces that are framework-agnostic and easy to use. It allows you to create dynamic web applications with a simple, declarative API similar to Streamlit, but designed to work with any HTTP framework (Flask, FastAPI, Django, etc.).

## ✨ Features

- **Framework Agnostic**: Works with any Python web framework (Flask, FastAPI, Django, etc.)
- **Declarative UI**: Build interfaces using simple Python functions
- **Interactive Components**: Buttons, forms, inputs, selects, checkboxes, and more
- **State Management**: Built-in session state management
- **Reactive Updates**: Automatic UI updates based on user interactions
- **Fragment Support**: Partial page updates for better performance
- **Flexible Layouts**: Containers, columns, flex layouts, and expandable sections
- **Rich Content**: Support for markdown, images, and custom styling

## 🚀 Installation

Install routelit using pip:

```bash
pip install routelit
# or
uv add routelit
```

## 📖 Quick Start

Here's a simple example of how to use routelit with Flask:

```bash
uv add routelit-flask
```

```python
from flask import Flask
from routelit import RouteLit, RouteLitBuilder
from routelit_flask import RouteLitFlaskAdapter

app = Flask(__name__)

rl = RouteLit()
rl_adapter = RouteLitFlaskAdapter(rl).configure(app)

def index_view(rl: RouteLitBuilder):
    rl.text("Hello, World!")

@app.route("/", methods=["GET", "POST"])
def index():
    return rl_adapter.response(index_view)
```
