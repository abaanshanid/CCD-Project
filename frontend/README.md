# PixelBatch frontend

React/Vite frontend for the CCD AWS batch image processor.

## Setup

1. Get the deployed API URL from the project Terraform folder:

   ```powershell
   terraform "-chdir=..\terraform" output -raw api_url
   ```

2. Copy `.env.example` to `.env` and replace the value with that URL:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

3. Install and run:

   ```powershell
   npm install
   npm run dev
   ```

4. Open `http://localhost:5173`.

## Production build

```powershell
npm run build
```

The optimized static frontend is written to `dist`.

## Supported workflow

- Select up to 50 JPG, PNG, or WEBP images.
- Configure resize, rotation, flip, crop, background removal, format, and quality.
- Upload directly to S3 using presigned URLs.
- Start asynchronous SQS/Lambda processing.
- Poll DynamoDB-backed batch progress.
- Highlight exact and visually similar duplicates without skipping them.
- Preview and download every successful result.
