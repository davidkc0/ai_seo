// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';

export default defineConfig({
  site: 'https://illusion.ai',
  integrations: [mdx()],
  base: '/blog',
  trailingSlash: 'never',
  build: {
    format: 'directory',
  },
});
