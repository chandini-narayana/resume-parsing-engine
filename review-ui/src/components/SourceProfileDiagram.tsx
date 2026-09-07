/**
 * A small, literal CSS diagram: raw text lines resolving into labeled
 * structured rows. Decorative illustration of what the pipeline actually
 * does (see docs/architecture.md's Upload -> Parse -> Extract -> Profile
 * flow) -- not a generic hero graphic, so it's aria-hidden and the real
 * explanation lives in the surrounding text/copy.
 */
export function SourceProfileDiagram() {
  return (
    <div className="sp-diagram" aria-hidden="true">
      <div className="sp-diagram__panel sp-diagram__panel--source">
        <span className="sp-diagram__line" style={{ width: "88%" }} />
        <span className="sp-diagram__line" style={{ width: "62%" }} />
        <span className="sp-diagram__line" style={{ width: "74%" }} />
        <span className="sp-diagram__line" style={{ width: "45%" }} />
      </div>
      <span className="sp-diagram__arrow">&rarr;</span>
      <div className="sp-diagram__panel sp-diagram__panel--profile">
        <span className="sp-diagram__row">
          <span className="sp-diagram__dot" />
          <span className="sp-diagram__bar" style={{ width: "70%" }} />
        </span>
        <span className="sp-diagram__row">
          <span className="sp-diagram__dot" />
          <span className="sp-diagram__bar" style={{ width: "50%" }} />
        </span>
        <span className="sp-diagram__row">
          <span className="sp-diagram__dot" />
          <span className="sp-diagram__bar" style={{ width: "80%" }} />
        </span>
      </div>
    </div>
  );
}
