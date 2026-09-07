const STEPS = [
  { title: "Upload", body: "Drop a PDF or DOCX resume." },
  { title: "Parse & segment", body: "Layout, tables, and sections are recovered from the raw file." },
  {
    title: "Extract & score",
    body: "Contact, skills, experience, and education are pulled out and confidence-scored.",
  },
  { title: "Review & correct", body: "You inspect the evidence, fix what's wrong, and it's saved." },
] as const;

export function WorkflowRail() {
  return (
    <ol className="workflow-rail">
      {STEPS.map((step, index) => (
        <li className="workflow-rail__step" key={step.title}>
          <span className="workflow-rail__node" aria-hidden="true">
            {index + 1}
          </span>
          <div>
            <div className="workflow-rail__title">{step.title}</div>
            <p className="workflow-rail__body">{step.body}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
