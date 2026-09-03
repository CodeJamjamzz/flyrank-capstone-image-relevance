# Capstone constraints

## Repository and cost

This capstone must live in one separate, public GitHub repository from the first day of development. Do not place it inside a repository that contains other work.

The complete project must remain at zero cost and must not require a credit card. Use free tools and services only. If a workflow asks for payment details or a credit card, stop and choose the documented free alternative.

## AI and model use

AI-assisted development is encouraged, but the work remains owned by the project author. Maintain an honest `BUILDLOG.md` that records where AI helped, where its output was incorrect or incomplete, and what changed as a result. The author must be able to explain any two or three lines of code selected by an evaluator. "AI wrote it" is not an acceptable explanation.

For any AI or vision capability, use Gemini Flash's free tier with a Google account and no card, or fully local models through Ollama. Keep the evaluation corpus small so each run remains inexpensive. Use batch jobs and explicit cost tracking to make model usage visible.

Never trust invalid model output. Validate every vision-model response against the project schema. Retry failures when appropriate or flag them for review. Never silently accept invalid output.

## Corpus and reproducibility

Use only licensed-free images in any corpus, such as images from Unsplash or Pexels. Link the source license information in the corpus documentation. Keep the corpus small and either commit it to the repository or provide a deterministic download script so evaluators can reproduce results.

## Secrets

Store API keys and secrets in `.env` only. Keep `.env` ignored by Git, commit `.env.example` with empty values, and never hard-code credentials or commit secrets.
