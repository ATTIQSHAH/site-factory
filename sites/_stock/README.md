# Curated stock image library

This folder is the local, API-independent stock library used by the website factory.
Only add images that you have the right to use commercially in client-facing demo
websites. Do not download random images from Google Images or copy photos from other
businesses.

## Folder layout

```text
sites/_stock/
  manifest.json
  restaurant/{food,interior,exterior,dining,people,detail}/
  cafe/{interior,coffee,food,lifestyle,exterior,detail}/
  coffee/{coffee,interior,barista,beans,food,exterior}/
  fastfood/{burger,pizza,fried-chicken,fries,food,interior,exterior,people}/
  shared/
```

Use descriptive filenames, for example `fastfood/burger/smash-burger-closeup-01.jpg`.
The selector also reads subject words from folder names and filenames, so these labels
matter. Keep images landscape, ideally at least 1600 x 1000 pixels, sharp, and free of
watermarks, logos, text overlays, or heavy filters.

## License and attribution record

For every new image, add an entry to `manifest.json` keyed by its path relative to this
folder. Record the creator, source page, exact license, and any required attribution.
Keep proof of the license/source. Do not add an image if commercial use or modification
is not permitted.

Example:

```json
{
  "restaurant/food/roast-chicken-01.jpg": {
    "creator": "Photographer name",
    "source_url": "https://example.com/photo-page",
    "license": "CC0-1.0",
    "attribution": "Photographer name",
    "tags": ["food", "roast chicken", "restaurant"]
  }
}
```

The manifest is an asset register, not a substitute for checking the actual license.
Prefer CC0, public-domain, or another license that clearly permits commercial use and
modification. Follow attribution requirements where they apply.

## Selection behavior

The factory first uses suitable photos from the business's own website. It then fills
gaps with relevant local images, prioritizing the business category and rotating across
subjects. Stock photos are illustrative and must never be represented as photos of the
actual business, its premises, staff, or exact menu items.
