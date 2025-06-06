# routelit

[![Release](https://img.shields.io/github/v/release/routelit/routelit)](https://img.shields.io/github/v/release/routelit/routelit)
[![Build status](https://img.shields.io/github/actions/workflow/status/routelit/routelit/main.yml?branch=main)](https://github.com/routelit/routelit/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/routelit/routelit/branch/main/graph/badge.svg)](https://codecov.io/gh/routelit/routelit)
[![Commit activity](https://img.shields.io/github/commit-activity/m/routelit/routelit)](https://img.shields.io/github/commit-activity/m/routelit/routelit)
[![License](https://img.shields.io/github/license/routelit/routelit)](https://img.shields.io/github/license/routelit/routelit)

![Routelit](https://wsrv.nl/?url=res.cloudinary.com/rolangom/image/upload/v1747976918/routelit/routelit_c2otsv.png&w=300&h=300)

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
```

## 📖 Quick Start

Here's a simple example of how to use routelit:

```python
from routelit import RouteLit, RouteLitBuilder

# Create a RouteLit instance
rl = RouteLit()

def my_app(builder: RouteLitBuilder):
    builder.title("Welcome to RouteLit!")

    name = builder.text_input("Enter your name:", value="World")

    if builder.button("Say Hello"):
        builder.text(f"Hello, {name}!")

    builder.markdown("This is a **markdown** text with *emphasis*.")

# Use with your preferred web framework
# Example with Flask:
from flask import Flask, request

app = Flask(__name__)

flask_adapter = ... # TODO: publish package for this

@app.route("/", methods=["GET", "POST"])
def index():

    # Return HTML response
    return flask_adapter.response(my_app)
```

## 🏗️ Core Concepts

### Builder Pattern
RouteLit uses a builder pattern where you define your UI using a `RouteLitBuilder` instance:

```python
def my_view(builder: RouteLitBuilder):
    builder.header("My Application")

    with builder.container():
        builder.text("This is inside a container")

        col1, col2 = builder.columns(2)
        with col1:
            builder.text("Left column")
        with col2:
            builder.text("Right column")
```

### State Management
RouteLit automatically manages state between requests:

```python
def counter_app(builder: RouteLitBuilder):
    # Get current count from session state
    count = builder.session_state.get("count", 0)

    builder.text(f"Count: {count}")

    if builder.button("Increment"):
        builder.session_state["count"] = count + 1
        builder.rerun()  # Trigger a re-render
```

### Interactive Components
Build rich forms and interactive elements:

```python
def form_example(builder: RouteLitBuilder):
    with builder.form("my_form"):
        name = builder.text_input("Name")
        age = builder.text_input("Age", type="number")

        options = ["Option 1", "Option 2", "Option 3"]
        choice = builder.select("Choose an option", options)

        newsletter = builder.checkbox("Subscribe to newsletter")

        if builder.button("Submit", event_name="submit"):
            builder.text(f"Hello {name}, you are {age} years old!")
            if newsletter:
                builder.text("Thanks for subscribing!")
```

## 🔧 Framework Integration

RouteLit is designed to work with any Python web framework.
TODO: Add framework integration examples.

## 📚 Documentation

- **Github repository**: <https://github.com/routelit/routelit/>
- **Documentation**: <https://routelit.github.io/routelit/>

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

RouteLit is inspired by [Streamlit](https://streamlit.io/) but designed to be framework-agnostic and more flexible for web development use cases.

---

Repository initiated with [fpgmaas/cookiecutter-uv](https://github.com/fpgmaas/cookiecutter-uv).
