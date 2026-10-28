"use client";
import "ol/ol.css";
import { useEffect, useRef } from "react";
import { Async, Head } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

export default function MapPage() {
  const { data, error, loading, reload } = useLoad(() => api<any>("/shops"));
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!data || !box.current) return;
    let map: any;
    (async () => {
      const [{ default: OlMap }, { default: View }, { default: TileLayer }, { default: VectorLayer }, { default: VectorSource },
             { default: Feature }, { default: Point }, { fromLonLat }, { Style, Circle, Fill, Stroke }, { default: OSM }] = await Promise.all([
        import("ol/Map"), import("ol/View"), import("ol/layer/Tile"), import("ol/layer/Vector"), import("ol/source/Vector"),
        import("ol/Feature"), import("ol/geom/Point"), import("ol/proj"), import("ol/style"), import("ol/source/OSM"),
      ]);
      const dot = (color: string, r: number) => new Style({ image: new Circle({ radius: r, fill: new Fill({ color }), stroke: new Stroke({ color: "#fff", width: 2 }) }) });
      const mine = new Feature(new Point(fromLonLat([data.me.lng, data.me.lat])));
      mine.setStyle(dot("#B38547", 9));
      const others = data.nearby.map((s: any) => {
        const f = new Feature(new Point(fromLonLat([s.lng, s.lat])));
        f.setStyle(dot("#2E2A25", 7));
        return f;
      });
      map = new OlMap({
        target: box.current!,
        layers: [new TileLayer({ source: new OSM() }), new VectorLayer({ source: new VectorSource({ features: [mine, ...others] }) })],
        view: new View({ center: fromLonLat([data.me.lng, data.me.lat]), zoom: 14 }),
      });
    })();
    return () => map?.setTarget(undefined);
  }, [data]);

  return (
    <>
      <Head title="Mohalla map" sub={data ? `${data.nearby.length} dukaan ${data.radius_km} km ke andar. Peela dot aapki dukaan hai.` : undefined} />
      <Async loading={loading} error={error} reload={reload}>
        <div className="map" ref={box} />
        <p className="note">Doosri dukaanon ka stock aur khata aapko nahi dikhta. Sirf naam aur doori.</p>
        {data ? (
          <ul className="log">{data.nearby.map((s: any) => <li key={s.id}>{s.name}, {s.area}: {s.distance_km} km</li>)}</ul>
        ) : null}
      </Async>
    </>
  );
}