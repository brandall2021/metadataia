export type ProviderType =
  | "openai"
  | "openai-compatible"
  | "ollama"
  | "anthropic"
  | "google"
  | "azure-openai";

export type ProviderCategory = "frontier" | "fast" | "open" | "aggregator" | "local" | "enterprise";

export type SuggestedModel = {
  name: string;
  modelIdentifier: string;
  contextWindow?: number;
  supportsJson?: boolean;
  supportsVision?: boolean;
  note?: string;
};

export type ProviderPreset = {
  code: string;
  name: string;
  type: ProviderType;
  baseUrl: string;
  docsUrl: string;
  keysUrl?: string;
  category: ProviderCategory;
  description: string;
  requiresKey: boolean;
  configuration?: Record<string, unknown>;
  models: SuggestedModel[];
};

export const PROVIDER_TYPE_LABELS: Record<ProviderType, string> = {
  openai: "OpenAI",
  "openai-compatible": "Compatible OpenAI",
  ollama: "Ollama",
  anthropic: "Anthropic",
  google: "Google Gemini",
  "azure-openai": "Azure OpenAI",
};

export const PROVIDER_TYPE_OPTIONS: { value: ProviderType; label: string }[] = (
  Object.keys(PROVIDER_TYPE_LABELS) as ProviderType[]
).map((value) => ({ value, label: PROVIDER_TYPE_LABELS[value] }));

export const PROVIDER_CATEGORIES: { value: ProviderCategory | "all"; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "frontier", label: "Frontera" },
  { value: "fast", label: "Alta velocidad" },
  { value: "open", label: "Open weights" },
  { value: "aggregator", label: "Agregadores" },
  { value: "enterprise", label: "Nube / Empresa" },
  { value: "local", label: "Local" },
];

export const PROVIDER_CATALOG: ProviderPreset[] = [
  {
    code: "openai",
    name: "OpenAI",
    type: "openai",
    baseUrl: "https://api.openai.com/v1",
    docsUrl: "https://platform.openai.com/docs/api-reference",
    keysUrl: "https://platform.openai.com/api-keys",
    category: "frontier",
    description: "Modelos GPT, razonamiento o-series y visión. Referencia del estándar de la API.",
    requiresKey: true,
    models: [
      { name: "GPT-5", modelIdentifier: "gpt-5", contextWindow: 400000, supportsJson: true, supportsVision: true },
      { name: "GPT-4.1 mini", modelIdentifier: "gpt-4.1-mini", contextWindow: 1047576, supportsJson: true, supportsVision: true },
      { name: "GPT-4o", modelIdentifier: "gpt-4o", contextWindow: 128000, supportsJson: true, supportsVision: true },
      { name: "GPT-4o mini", modelIdentifier: "gpt-4o-mini", contextWindow: 128000, supportsJson: true, supportsVision: true },
      { name: "o4-mini", modelIdentifier: "o4-mini", contextWindow: 200000, supportsJson: true, supportsVision: true },
    ],
  },
  {
    code: "anthropic",
    name: "Anthropic",
    type: "anthropic",
    baseUrl: "https://api.anthropic.com",
    docsUrl: "https://docs.anthropic.com/en/api/messages",
    keysUrl: "https://console.anthropic.com/settings/keys",
    category: "frontier",
    description: "Claude Sonnet, Haiku y Opus. API nativa /v1/messages con gran desempeño en documentos largos.",
    requiresKey: true,
    models: [
      { name: "Claude Sonnet 4.5", modelIdentifier: "claude-sonnet-4-5", contextWindow: 200000, supportsJson: true, supportsVision: true },
      { name: "Claude Haiku 4.5", modelIdentifier: "claude-haiku-4-5", contextWindow: 200000, supportsJson: true, supportsVision: true },
      { name: "Claude Opus 4.1", modelIdentifier: "claude-opus-4-1", contextWindow: 200000, supportsJson: true, supportsVision: true },
    ],
  },
  {
    code: "google",
    name: "Google Gemini",
    type: "google",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    docsUrl: "https://ai.google.dev/gemini-api/docs/openai",
    keysUrl: "https://aistudio.google.com/app/apikey",
    category: "frontier",
    description: "Gemini vía capa compatible OpenAI. Ventanas de hasta 1M de tokens, ideal para expedientes completos.",
    requiresKey: true,
    models: [
      { name: "Gemini 2.5 Pro", modelIdentifier: "gemini-2.5-pro", contextWindow: 1048576, supportsJson: true, supportsVision: true },
      { name: "Gemini 2.5 Flash", modelIdentifier: "gemini-2.5-flash", contextWindow: 1048576, supportsJson: true, supportsVision: true },
      { name: "Gemini 2.5 Flash Lite", modelIdentifier: "gemini-2.5-flash-lite", contextWindow: 1048576, supportsJson: true },
      { name: "Gemini 2.0 Flash", modelIdentifier: "gemini-2.0-flash", contextWindow: 1048576, supportsJson: true, supportsVision: true },
    ],
  },
  {
    code: "azure-openai",
    name: "Azure OpenAI",
    type: "azure-openai",
    baseUrl: "https://TU-RECURSO.openai.azure.com/openai/deployments/TU-DEPLOYMENT",
    docsUrl: "https://learn.microsoft.com/azure/ai-services/openai/reference",
    keysUrl: "https://portal.azure.com",
    category: "enterprise",
    description:
      "Deployments de OpenAI dentro de Azure. La Base URL debe incluir el deployment; la API key se envía en el header api-key.",
    requiresKey: true,
    configuration: { api_version: "2024-10-21" },
    models: [],
  },
  {
    code: "deepseek",
    name: "DeepSeek",
    type: "openai-compatible",
    baseUrl: "https://api.deepseek.com/v1",
    docsUrl: "https://api-docs.deepseek.com",
    keysUrl: "https://platform.deepseek.com/api_keys",
    category: "open",
    description: "Modelos de razonamiento y chat con costo muy bajo. Excelente para extracción masiva.",
    requiresKey: true,
    models: [
      { name: "DeepSeek Chat", modelIdentifier: "deepseek-chat", contextWindow: 128000, supportsJson: true },
      { name: "DeepSeek Reasoner", modelIdentifier: "deepseek-reasoner", contextWindow: 128000 },
    ],
  },
  {
    code: "mistral",
    name: "Mistral AI",
    type: "openai-compatible",
    baseUrl: "https://api.mistral.ai/v1",
    docsUrl: "https://docs.mistral.ai/api",
    keysUrl: "https://console.mistral.ai/api-keys",
    category: "open",
    description: "Modelos europeos con opción on-premise. Mistral Large, Small, Codestral y Pixtral.",
    requiresKey: true,
    models: [
      { name: "Mistral Large", modelIdentifier: "mistral-large-latest", contextWindow: 131000, supportsJson: true },
      { name: "Mistral Small", modelIdentifier: "mistral-small-latest", contextWindow: 131000, supportsJson: true },
      { name: "Pixtral Large", modelIdentifier: "pixtral-large-latest", contextWindow: 128000, supportsJson: true, supportsVision: true },
      { name: "Codestral", modelIdentifier: "codestral-latest", contextWindow: 256000, supportsJson: true },
    ],
  },
  {
    code: "groq",
    name: "Groq",
    type: "openai-compatible",
    baseUrl: "https://api.groq.com/openai/v1",
    docsUrl: "https://console.groq.com/docs/api-reference",
    keysUrl: "https://console.groq.com/keys",
    category: "fast",
    description: "Inferencia LPU de baja latencia sobre modelos abiertos. Muy útil para OCR asistido y clasificación.",
    requiresKey: true,
    models: [
      { name: "Llama 3.3 70B", modelIdentifier: "llama-3.3-70b-versatile", contextWindow: 131072, supportsJson: true },
      { name: "Llama 3.1 8B", modelIdentifier: "llama-3.1-8b-instant", contextWindow: 131072, supportsJson: true },
      { name: "Qwen3 32B", modelIdentifier: "qwen/qwen3-32b", contextWindow: 131072, supportsJson: true },
      { name: "Kimi K2", modelIdentifier: "moonshotai/kimi-k2-instruct", contextWindow: 262144, supportsJson: true },
    ],
  },
  {
    code: "xai",
    name: "xAI",
    type: "openai-compatible",
    baseUrl: "https://api.x.ai/v1",
    docsUrl: "https://docs.x.ai/docs/api-reference",
    keysUrl: "https://console.x.ai",
    category: "frontier",
    description: "Modelos Grok con contexto amplio y soporte de visión.",
    requiresKey: true,
    models: [
      { name: "Grok 4", modelIdentifier: "grok-4", contextWindow: 256000, supportsJson: true, supportsVision: true },
      { name: "Grok 3", modelIdentifier: "grok-3", contextWindow: 131072, supportsJson: true },
      { name: "Grok 3 Mini", modelIdentifier: "grok-3-mini", contextWindow: 131072, supportsJson: true },
    ],
  },
  {
    code: "openrouter",
    name: "OpenRouter",
    type: "openai-compatible",
    baseUrl: "https://openrouter.ai/api/v1",
    docsUrl: "https://openrouter.ai/docs/api-reference/overview",
    keysUrl: "https://openrouter.ai/keys",
    category: "aggregator",
    description: "Una sola clave para cientos de modelos de distintos proveedores. Permite comparar y conmutar agentes.",
    requiresKey: true,
    models: [
      { name: "Claude Sonnet 4.5", modelIdentifier: "anthropic/claude-sonnet-4.5", contextWindow: 200000, supportsJson: true, supportsVision: true },
      { name: "GPT-4o mini", modelIdentifier: "openai/gpt-4o-mini", contextWindow: 128000, supportsJson: true, supportsVision: true },
      { name: "Gemini 2.5 Flash", modelIdentifier: "google/gemini-2.5-flash", contextWindow: 1048576, supportsJson: true, supportsVision: true },
      { name: "DeepSeek Chat", modelIdentifier: "deepseek/deepseek-chat", contextWindow: 128000, supportsJson: true },
    ],
  },
  {
    code: "together",
    name: "Together AI",
    type: "openai-compatible",
    baseUrl: "https://api.together.xyz/v1",
    docsUrl: "https://docs.together.ai/reference",
    keysUrl: "https://api.together.ai/settings/api-keys",
    category: "open",
    description: "Hosting de modelos open weights con endpoints compatibles OpenAI y fine-tuning.",
    requiresKey: true,
    models: [
      { name: "Llama 3.3 70B Turbo", modelIdentifier: "meta-llama/Llama-3.3-70B-Instruct-Turbo", contextWindow: 131072, supportsJson: true },
      { name: "Qwen 2.5 72B Turbo", modelIdentifier: "Qwen/Qwen2.5-72B-Instruct-Turbo", contextWindow: 32768, supportsJson: true },
      { name: "DeepSeek R1", modelIdentifier: "deepseek-ai/DeepSeek-R1", contextWindow: 163840 },
    ],
  },
  {
    code: "fireworks",
    name: "Fireworks AI",
    type: "openai-compatible",
    baseUrl: "https://api.fireworks.ai/inference/v1",
    docsUrl: "https://docs.fireworks.ai/api-reference/introduction",
    keysUrl: "https://fireworks.ai/account/api-keys",
    category: "open",
    description: "Inferencia rápida de modelos abiertos y modelos propios ajustados.",
    requiresKey: true,
    models: [
      { name: "Llama 3.3 70B", modelIdentifier: "accounts/fireworks/models/llama-v3p3-70b-instruct", contextWindow: 131072, supportsJson: true },
      { name: "DeepSeek R1", modelIdentifier: "accounts/fireworks/models/deepseek-r1", contextWindow: 163840 },
    ],
  },
  {
    code: "perplexity",
    name: "Perplexity",
    type: "openai-compatible",
    baseUrl: "https://api.perplexity.ai",
    docsUrl: "https://docs.perplexity.ai/api-reference/chat-completions",
    keysUrl: "https://www.perplexity.ai/settings/api",
    category: "aggregator",
    description: "Modelos Sonar con búsqueda web integrada. Útil para verificar datos bibliográficos.",
    requiresKey: true,
    configuration: { probe_model: "sonar" },
    models: [
      { name: "Sonar", modelIdentifier: "sonar", contextWindow: 131072 },
      { name: "Sonar Pro", modelIdentifier: "sonar-pro", contextWindow: 200000 },
      { name: "Sonar Reasoning", modelIdentifier: "sonar-reasoning", contextWindow: 131072 },
    ],
  },
  {
    code: "cohere",
    name: "Cohere",
    type: "openai-compatible",
    baseUrl: "https://api.cohere.ai/compatibility/v1",
    docsUrl: "https://docs.cohere.com/reference/chat",
    keysUrl: "https://dashboard.cohere.com/api-keys",
    category: "enterprise",
    description: "Command R orientado a RAG y documentos empresariales, con endpoint compatible OpenAI.",
    requiresKey: true,
    models: [
      { name: "Command R+", modelIdentifier: "command-r-plus-08-2024", contextWindow: 128000, supportsJson: true },
      { name: "Command R", modelIdentifier: "command-r-08-2024", contextWindow: 128000, supportsJson: true },
      { name: "Command R7B", modelIdentifier: "command-r7b-12-2024", contextWindow: 128000 },
    ],
  },
  {
    code: "cerebras",
    name: "Cerebras",
    type: "openai-compatible",
    baseUrl: "https://api.cerebras.ai/v1",
    docsUrl: "https://inference-docs.cerebras.ai",
    keysUrl: "https://cloud.cerebras.ai",
    category: "fast",
    description: "Inferencia de muy alta velocidad en obleas de silicio. Modelos abiertos populares.",
    requiresKey: true,
    models: [
      { name: "Llama 3.3 70B", modelIdentifier: "llama-3.3-70b", contextWindow: 131072, supportsJson: true },
      { name: "Qwen3 32B", modelIdentifier: "qwen-3-32b", contextWindow: 131072, supportsJson: true },
    ],
  },
  {
    code: "sambanova",
    name: "SambaNova",
    type: "openai-compatible",
    baseUrl: "https://api.sambanova.ai/v1",
    docsUrl: "https://docs.sambanova.ai/cloud/docs/get-started/overview",
    keysUrl: "https://cloud.sambanova.ai/apis",
    category: "fast",
    description: "Inferencia acelerada de modelos abiertos de gran tamaño.",
    requiresKey: true,
    models: [
      { name: "Llama 3.3 70B", modelIdentifier: "Meta-Llama-3.3-70B-Instruct", contextWindow: 131072, supportsJson: true },
      { name: "DeepSeek R1", modelIdentifier: "DeepSeek-R1", contextWindow: 163840 },
    ],
  },
  {
    code: "nvidia",
    name: "NVIDIA NIM",
    type: "openai-compatible",
    baseUrl: "https://integrate.api.nvidia.com/v1",
    docsUrl: "https://docs.nvidia.com/nim",
    keysUrl: "https://build.nvidia.com",
    category: "enterprise",
    description: "Catálogo NIM de NVIDIA con modelos abiertos optimizados y endpoints OpenAI.",
    requiresKey: true,
    models: [
      { name: "Llama 3.3 70B", modelIdentifier: "meta/llama-3.3-70b-instruct", contextWindow: 131072, supportsJson: true },
      { name: "Nemotron 70B", modelIdentifier: "nvidia/llama-3.1-nemotron-70b-instruct", contextWindow: 131072, supportsJson: true },
    ],
  },
  {
    code: "github-models",
    name: "GitHub Models",
    type: "openai-compatible",
    baseUrl: "https://models.github.ai/inference",
    docsUrl: "https://docs.github.com/en/github-models",
    keysUrl: "https://github.com/settings/tokens",
    category: "aggregator",
    description: "Acceso a modelos de varios proveedores con un token de GitHub. Útil para pruebas académicas.",
    requiresKey: true,
    models: [
      { name: "GPT-4o", modelIdentifier: "openai/gpt-4o", contextWindow: 128000, supportsJson: true, supportsVision: true },
      { name: "GPT-4o mini", modelIdentifier: "openai/gpt-4o-mini", contextWindow: 128000, supportsJson: true, supportsVision: true },
      { name: "Llama 3.3 70B", modelIdentifier: "meta/Llama-3.3-70B-Instruct", contextWindow: 131072, supportsJson: true },
    ],
  },
  {
    code: "huggingface",
    name: "Hugging Face Router",
    type: "openai-compatible",
    baseUrl: "https://router.huggingface.co/v1",
    docsUrl: "https://huggingface.co/docs/inference-providers",
    keysUrl: "https://huggingface.co/settings/tokens",
    category: "aggregator",
    description: "Router de Inference Providers de Hugging Face con endpoints compatibles OpenAI.",
    requiresKey: true,
    models: [
      { name: "Llama 3.3 70B", modelIdentifier: "meta-llama/Llama-3.3-70B-Instruct", contextWindow: 131072, supportsJson: true },
      { name: "Qwen 2.5 72B", modelIdentifier: "Qwen/Qwen2.5-72B-Instruct", contextWindow: 32768, supportsJson: true },
    ],
  },
  {
    code: "qwen",
    name: "Alibaba Qwen",
    type: "openai-compatible",
    baseUrl: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    docsUrl: "https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope",
    keysUrl: "https://bailian.console.alibabacloud.com",
    category: "open",
    description: "Modelos Qwen con modo compatible OpenAI (región internacional de DashScope).",
    requiresKey: true,
    models: [
      { name: "Qwen Max", modelIdentifier: "qwen-max", contextWindow: 32768, supportsJson: true },
      { name: "Qwen Plus", modelIdentifier: "qwen-plus", contextWindow: 131072, supportsJson: true },
      { name: "Qwen Turbo", modelIdentifier: "qwen-turbo", contextWindow: 131072, supportsJson: true },
    ],
  },
  {
    code: "moonshot",
    name: "Moonshot (Kimi)",
    type: "openai-compatible",
    baseUrl: "https://api.moonshot.ai/v1",
    docsUrl: "https://platform.moonshot.ai/docs",
    keysUrl: "https://platform.moonshot.ai/console/api-keys",
    category: "open",
    description: "Modelos Kimi con contexto largo, orientados a lectura de documentos extensos.",
    requiresKey: true,
    models: [
      { name: "Kimi K2", modelIdentifier: "kimi-k2-0711-preview", contextWindow: 131072, supportsJson: true },
      { name: "Moonshot 128K", modelIdentifier: "moonshot-v1-128k", contextWindow: 131072, supportsJson: true },
    ],
  },
  {
    code: "zhipu",
    name: "Zhipu GLM",
    type: "openai-compatible",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    docsUrl: "https://docs.bigmodel.cn",
    keysUrl: "https://open.bigmodel.cn/usercenter/apikeys",
    category: "open",
    description: "Familia GLM-4 de Zhipu con API compatible OpenAI.",
    requiresKey: true,
    models: [
      { name: "GLM-4 Plus", modelIdentifier: "glm-4-plus", contextWindow: 128000, supportsJson: true },
      { name: "GLM-4 Flash", modelIdentifier: "glm-4-flash", contextWindow: 128000, supportsJson: true },
    ],
  },
  {
    code: "ollama",
    name: "Ollama",
    type: "ollama",
    baseUrl: "http://127.0.0.1:11434/v1",
    docsUrl: "https://github.com/ollama/ollama/blob/main/docs/api.md",
    category: "local",
    description:
      "Modelos locales sin costo por token. En Docker, 127.0.0.1 es el contenedor: usá el host o IP del equipo que corre Ollama.",
    requiresKey: false,
    models: [
      { name: "Llama 3.2 3B", modelIdentifier: "llama3.2", contextWindow: 131072, supportsJson: true },
      { name: "Qwen 2.5 7B", modelIdentifier: "qwen2.5", contextWindow: 32768, supportsJson: true },
      { name: "Gemma 3", modelIdentifier: "gemma3", contextWindow: 131072 },
      { name: "DeepSeek R1 8B", modelIdentifier: "deepseek-r1", contextWindow: 131072 },
    ],
  },
  {
    code: "lmstudio",
    name: "LM Studio",
    type: "openai-compatible",
    baseUrl: "http://127.0.0.1:1234/v1",
    docsUrl: "https://lmstudio.ai/docs/app/api/endpoints/openai",
    category: "local",
    description: "Servidor local compatible OpenAI para modelos GGUF. Usá el identificador que muestra LM Studio.",
    requiresKey: false,
    models: [
      { name: "Modelo local", modelIdentifier: "local-model", contextWindow: 32768, supportsJson: true },
    ],
  },
  {
    code: "vllm",
    name: "vLLM",
    type: "openai-compatible",
    baseUrl: "http://127.0.0.1:8000/v1",
    docsUrl: "https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html",
    category: "local",
    description: "Servidor de alta concurrencia para modelos abiertos. El identificador es el nombre con el que se sirvió el modelo.",
    requiresKey: false,
    models: [
      { name: "Llama 3.1 8B", modelIdentifier: "meta-llama/Llama-3.1-8B-Instruct", contextWindow: 131072, supportsJson: true },
    ],
  },
  {
    code: "llamacpp",
    name: "llama.cpp",
    type: "openai-compatible",
    baseUrl: "http://127.0.0.1:8080/v1",
    docsUrl: "https://github.com/ggml-org/llama.cpp/blob/master/examples/server/README.md",
    category: "local",
    description: "Servidor liviano de llama.cpp con endpoint compatible OpenAI.",
    requiresKey: false,
    models: [{ name: "Modelo local", modelIdentifier: "local-model", contextWindow: 32768 }],
  },
  {
    code: "custom",
    name: "Otro compatible OpenAI",
    type: "openai-compatible",
    baseUrl: "",
    docsUrl: "https://platform.openai.com/docs/api-reference",
    category: "enterprise",
    description: "Cualquier servicio con /chat/completions compatible OpenAI (proxy, gateway o servidor propio).",
    requiresKey: true,
    models: [],
  },
];

export function presetByCode(code: string | null | undefined): ProviderPreset | undefined {
  if (!code) return undefined;
  return PROVIDER_CATALOG.find((preset) => preset.code === code);
}

export function providerTypeLabel(type: string): string {
  return PROVIDER_TYPE_LABELS[type as ProviderType] ?? type;
}

export function nextAvailableCode(base: string, usedCodes: Set<string>): string {
  if (!usedCodes.has(base)) return base;
  let index = 2;
  while (usedCodes.has(`${base}-${index}`)) index += 1;
  return `${base}-${index}`;
}
