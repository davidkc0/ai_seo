// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';

export default defineConfig({
  integrations: [mdx()],
  base: '/blog',
  trailingSlash: 'never',
  build: {
    format: 'directory',
  },
});