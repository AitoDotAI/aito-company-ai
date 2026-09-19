# the provider is config-swappable; a missing key raises loudly

no LLM api key: set COMPANY_AI_LLM_API_KEY in the env file (the LLM surfaces need it; Aito access is separate)

# default provider resolves to an OpenAI-compatible client

provider=openai -> OpenAICompatClient model=gpt-5-mini

# Azure OpenAI: deployment URL, api-key auth, missing key raises

url: https://swedencentral.api.cognitive.microsoft.com/openai/deployments/gpt-5-mini/chat/completions?api-version=2024-08-01-preview
no Azure OpenAI key: set COMPANY_AI_LLM_API_KEY (or REACT_APP_OPENAI_MODEL_API_KEY) in the env file

# make_client routes the azure provider

provider=azure -> AzureOpenAIClient url=https://swedencentral.api.cognitive.microsoft.com/openai/deployments/gpt-5-mini/chat/completions?api-version=2024-08-01-preview
