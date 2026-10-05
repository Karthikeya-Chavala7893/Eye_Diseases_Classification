/**
 * app/layout.tsx
 * ──────────────
 * Root layout: fonts, metadata, global stylesheet and the auth provider.
 *
 * This is a Server Component. Only `AuthProvider` (and what it wraps) runs on
 * the client, so the shell stays server-rendered.
 */

import type { Metadata, Viewport } from 'next';
import { Inter, Plus_Jakarta_Sans } from 'next/font/google';

import { AuthProvider } from '@/context/AuthContext';
import { ChatBot } from '@/components/ChatBot';
import { KeepAlive } from '@/components/KeepAlive';

import './globals.css';

/** Display face for headings and the brand mark. */
const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '800'],
  variable: '--font-jakarta',
  display: 'swap',
});

/** Body face for running text. */
const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'VisionAI | AI-Powered Eye Care',
    template: '%s | VisionAI',
  },
  description:
    'VisionAI screens retinal fundus images for diabetic retinopathy, glaucoma, AMD, cataracts and more using an EfficientNetB0 deep-learning model.',
  applicationName: 'VisionAI',
  icons: {
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>👁️</text></svg>",
  },
  openGraph: {
    title: 'VisionAI | AI-Powered Eye Care',
    description: 'AI-powered retinal disease screening in under 30 seconds.',
    type: 'website',
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#0ea5e9',
};

/**
 * Wrap every route in the design-system shell.
 *
 * @param children The active route's rendered output.
 */
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>): JSX.Element {
  return (
    <html lang="en" className={`${jakarta.variable} ${inter.variable}`}>
      <body>
        <AuthProvider>
          {children}
          <ChatBot />
          <KeepAlive />
        </AuthProvider>
      </body>
    </html>
  );
}
