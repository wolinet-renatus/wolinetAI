---
license: mit
base_model:
- deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B
pipeline_tag: text-generation
library_name: transformers
---
library_name: transformers
base_model:
- deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B
pipeline_tag: text-generation
---

# Model Card for DeepSeek-R1-Distill-Qwen-1.5B-Uncensored

## Model Details

### Model Description

DeepSeek-R1-Distill-Qwen-1.5B-Uncensored is a text-generation model designed to uphold the values of internet freedom and unrestricted access to information. By offering an uncensored approach, this model enables users to explore ideas, generate content, and engage in discussions without the constraints of over-moderated or filtered outputs. It prioritizes user autonomy and aligns with principles of free speech and open knowledge sharing.

- **Developed by:** Thirdeye AI
- **Funded by:** Thirdeye AI
- **Shared by:** Thirdeye AI
- **Model type:** Distilled Transformer-based Language Model
- **Language(s) (NLP):** English
- **License:** Apache 2.0
- **Finetuned from model:** DeepSeek-R1-Distill-Qwen-1.5B

### Model Sources

- **Repository:** [DeepSeek-R1-Distill-Qwen-1.5B-Uncensored on Hugging Face](https://huggingface.co/thirdeyeai/DeepSeek-R1-Distill-Qwen-1.5B-uncensored)
- **Demo:** [Available on Hugging Face Hub](https://huggingface.co/thirdeyeai/DeepSeek-R1-Distill-Qwen-1.5B-uncensored)

---

## Uses

### Direct Use

The model is intended for applications that demand openness and flexibility in generating creative, exploratory, or critical content. These include:
- Free-form writing and storytelling
- Open-ended discussions
- Exploratory content generation for sensitive or nuanced topics

### Downstream Use

Users can fine-tune this model for specialized domains where censorship-free text generation is required, such as:
- Journalism and investigative research
- Creative projects that push artistic boundaries
- Academic applications exploring controversial or complex topics

### Out-of-Scope Use

This model should not be used for harmful, illegal, or unethical activities. Users must comply with applicable laws and ensure that the model's outputs do not infringe on others' rights.

---

## Bias, Risks, and Limitations

### Risks

While the uncensored approach promotes freedom, it may produce outputs that are controversial, offensive, or factually inaccurate. Users must exercise discretion when interpreting the model's outputs and take responsibility for their use.

### Recommendations

- Use responsibly, especially in contexts where outputs could impact individuals or communities.
- Employ content moderation or review processes for high-stakes applications.

---

## The Case for Uncensored Models

Thirdeye AI believes in the transformative power of open models that respect user autonomy and internet freedom. In a world where over-moderation can stifle innovation and critical thought, uncensored models empower individuals to explore and create without artificial constraints. This aligns with our mission to advance free and open access to AI tools.

By releasing this model, we aim to support the following:
- **Freedom of Expression:** Unrestricted AI tools enable users to articulate diverse perspectives and engage in meaningful conversations.
- **Transparency and Trust:** Users deserve access to tools that operate openly, fostering accountability and understanding of AI behaviors.
- **Creative Empowerment:** The absence of censorship allows for boundary-pushing content creation that might otherwise be suppressed.

---

## How to Get Started with the Model

```python
from transformers import pipeline

generator = pipeline("text-generation", model="thirdeyeai/DeepSeek-R1-Distill-Qwen-1.5B-uncensored")
response = generator("The importance of free speech is")
print(response)