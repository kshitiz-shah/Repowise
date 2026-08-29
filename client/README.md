# RepoWise client

Run the backend on port 3000 and the AI service on port 8000 first. Then:

```bash
cd client
cp .env.example .env
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). The browser talks only to the Node backend at `VITE_API_URL`; the backend keeps the AI service key private.
