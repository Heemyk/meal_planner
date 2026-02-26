# API

## Upload Recipes
`POST /api/recipes/upload`

- **Body:** multipart/form-data with `files` fields.
- **Response:** recipe count, ingredient count, SKU jobs enqueued.

## Create Plan
`POST /api/plan`

```json
{
  "target_servings": 12
}
```

Response contains solver status, objective, and selected recipe/SKU quantities.

## SKU Status
`GET /api/sku-status`

Returns which ingredients have price data (SKUs) and which are still pending (worker not done).

## Health
`GET /api/health`
