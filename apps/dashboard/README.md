This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Environment Variables

Create a `.env.local` file in the root of this directory with the following variables:

```bash
# API URL
NEXT_PUBLIC_API_URL=http://localhost:8001

# Google Places API Key (optional - for address autocomplete)
# See configuration instructions below
NEXT_PUBLIC_GOOGLE_PLACES_API_KEY=your_api_key_here
```

### Google Places API Configuration

The address input component supports autocomplete using Google Places API. To enable this feature:

1. **Get a Google Places API Key**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the "Places API (New)" API
   - Create credentials (API Key) in the Credentials section

2. **Configure API Key Restrictions** (IMPORTANT for security):
   - **HTTP referrer restrictions**: Add your domains:
     - `localhost` (for development)
     - Your production domain (e.g., `https://yourdomain.com/*`)
   - **API restrictions**: Limit to "Places API (New)" only
   - **Quotas**: Set daily/monthly limits to prevent unexpected costs
   - **Monitoring**: Enable alerts in Google Cloud Console

3. **Add the key to your environment**:
   - Add `NEXT_PUBLIC_GOOGLE_PLACES_API_KEY=your_key_here` to `.env.local`

**Note**: Without the API key, address input will work in manual entry mode only. The first 10,000 requests per month are free, then pricing applies.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
