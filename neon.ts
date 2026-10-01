import { defineConfig } from '@neon/config/v1';

export default defineConfig({
  aiGateway: true,
  buckets: {
    'note-attachments': {
      access: 'private',
    },
  },
});