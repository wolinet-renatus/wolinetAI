export interface BrandingConfig {
  appName: string
  logoPath: string
  logoAlt: string
  subtitle: string
  description: string
  tagline: string
  gradientFrom: string
  gradientVia: string
  gradientTo: string
}

export const defaultBranding: BrandingConfig = {
  appName: 'Wolinet AI',
  logoPath: '/logo.png',
  logoAlt: 'Wolinet AI',
  subtitle: 'Wolinet AI Inference Platform is a sovereign, high-performance engine for distributed LLM, multimodal, and embedding model serving and acceleration.',
  description: 'Wolinet AI Inference Platform empowers you to deploy and serve state-of-the-art models locally or in the cloud with zero token costs, automatic model downloading, and OpenAI-compatible endpoints.',
  tagline: 'Sovereign AI Inference Platform',
  gradientFrom: 'indigo-500',
  gradientVia: 'purple-500',
  gradientTo: 'cyan-500',
}

export function getBrandingFromEnv(): BrandingConfig {
  return {
    appName: process.env.NEXT_PUBLIC_APP_NAME || defaultBranding.appName,
    logoPath: process.env.NEXT_PUBLIC_LOGO_PATH || defaultBranding.logoPath,
    logoAlt: process.env.NEXT_PUBLIC_LOGO_ALT || defaultBranding.logoAlt,
    subtitle: process.env.NEXT_PUBLIC_APP_SUBTITLE || defaultBranding.subtitle,
    description: process.env.NEXT_PUBLIC_APP_DESCRIPTION || defaultBranding.description,
    tagline: process.env.NEXT_PUBLIC_APP_TAGLINE || defaultBranding.tagline,
    gradientFrom: process.env.NEXT_PUBLIC_GRADIENT_FROM || defaultBranding.gradientFrom,
    gradientVia: process.env.NEXT_PUBLIC_GRADIENT_VIA || defaultBranding.gradientVia,
    gradientTo: process.env.NEXT_PUBLIC_GRADIENT_TO || defaultBranding.gradientTo,
  }
}
