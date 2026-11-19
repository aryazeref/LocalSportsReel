import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://localsportreel.netlify.app";
  return ["", "/liiga/", "/predictions/", "/companion/", "/pricing/"].map(
    (path) => ({
      url: `${base}${path}`,
      lastModified: new Date(),
    })
  );
}