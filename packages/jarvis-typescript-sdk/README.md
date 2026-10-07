# @abdullahalrifat/jarvis-sdk

Small dependency-free TypeScript SDK for the Jarvis/AI Stack engineering API.

The SDK deliberately exposes only the stable control-plane operations: health, capabilities, run submission and cancellation. Provider credentials never belong in the SDK.

```ts
import { JarvisClient } from "@abdullahalrifat/jarvis-sdk";
const client = new JarvisClient({baseUrl: process.env.JARVIS_URL!, apiKey: process.env.JARVIS_API_KEY!});
const run = await client.run("run the unit tests");
```
