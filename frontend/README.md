# Qlib CN Stock Frontend

Vue 3 + Vite interactive dashboard for the Chinese stock market.

## Features
- **Market Sentiment**: Visualizes the `market_sentiment.csv` metrics via ECharts.
- **Market Topics**: Parses and displays the latest daily themes and related stocks.
- **AI Daily Reports**: Reads `zizizaizai_reports.json` and renders markdown news digests.
- **Stock Intraday & Research**: Shows minute-level K-lines and DeepSeek AI risk audits.

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

### Compile and Minify for Production

```sh
npm run build
```
