# 🧚 SynthGen AI

**A secure, scalable AI-powered synthetic data generator for developers and data scientists**

![SynthGen Screenshot](https://raw.githubusercontent.com/Jerryblessed/SynthGen/refs/heads/main/presentation/architectual_diagram.png?token=GHSAT0AAAAAADNAGIMHZXIBPVWX3KP4EVVQ2HNA4BQ)

---

## 📌 Overview

SynthGen AI is a web-based tool that allows users to upload a CSV schema and generate intelligent synthetic data for domains such as healthcare, finance, and retail. It supports both authenticated (Amazon Cognito) and guest sessions, enabling data generation with customizable parameters such as noise level, class balance, and PII masking.

Built using Flask and hosted on AWS Elastic Beanstalk, SynthGen stores generated records and user feedback in DynamoDB, while using Amazon Bedrock’s **Titan Text Lite** as the core LLM engine for synthetic data generation and chat guidance.

---

## 🚀 Features

- 📄 Upload CSV schema with headers
- 🏥 Choose domain (Health, Finance, Retail)
- 🎛 Customize record count, noise, and masking
- 🧠 AI assistant powered by Amazon Bedrock (Titan)
- 👥 AWS Cognito login + guest mode support
- 📦 Store data in DynamoDB
- 💬 Feedback collection interface
- ☁️ Hosted on AWS Elastic Beanstalk (EC2-based)

---

## 🛠 Built With

- **Frontend**: HTML5 + Bootstrap 5
- **Backend**: Python + Flask
- **AI/LLM**: Amazon Bedrock (`amazon.titan-text-lite-v1`, `us-east-1`)
- **Authentication**: AWS Cognito (Hosted UI)
- **Storage**: Amazon DynamoDB (`eu-north-1`)
- **Deployment**: AWS Elastic Beanstalk
- **Libraries**: Authlib, Boto3, Flask, Jinja2

---

## 📦 Installation

```bash
# Clone repository
$ git clone https://github.com/Jerryblessed/SynthGen.git
$ cd SynthGen

# (Optional) Create virtual environment
$ python -m venv venv
$ source venv/bin/activate  # or .\venv\Scripts\activate

# Install dependencies
$ pip install -r requirements.txt

# Run the Flask app
$ python app.py
```

---

## 🔐 Authentication

SynthGen supports user authentication using **Amazon Cognito Hosted UI**. On login, user email is fetched from token and used to store personalized data in DynamoDB.

Guest users can use all features but their data is **not stored**.

---

## 🧠 AI Agent

A Titan Text G1-Lite model from **Amazon Bedrock** powers:
- Friendly assistant that explains features
- Intelligent schema-aware data generation

Region: `us-east-1`

---

## 📂 Directory Structure

```
SynthGen/
├── app.py                  # Flask app entry point
├── templates/              # Jinja2 HTML templates
│   ├── base.html
│   ├── generate.html
│   ├── view.html
│   ├── feedback.html
│   └── agent.html
├── static/                 # (Optional) Static assets
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

---

## 💬 Feedback & Contributions

We welcome feedback and contributions!
- Create issues or pull requests
- Submit feedback via the app `/feedback` page

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

## 🔗 Live Demo

🌐 [http://synthgen.eu-north-1.elasticbeanstalk.com](http://synthgen.eu-north-1.elasticbeanstalk.com)

---

## 📽 Demo Video

🎥 [Watch the demo](https://vimeo.com/1100504622?share=copy) (3 min)

---

## 🙌 Credits

Developed by [Team Syntgen](https://github.com/Jerryblessed) for the AWS AI Agent Global Hackathon 2025.

---

## 📈 Slides

📊 [View the Solution Deck](https://docs.google.com/presentation/d/1svYJpYABIDAi4sxN2ZDW_NAeRsveqV2TTIqRN2vPPL8/edit?usp=sharing)
