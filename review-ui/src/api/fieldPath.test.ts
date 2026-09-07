import { describe, expect, it } from "vitest";
import { isValidFieldPath, scoredFieldPath } from "./fieldPath";

describe("isValidFieldPath", () => {
  it("accepts dotted and indexed paths matching the backend's contract", () => {
    expect(isValidFieldPath("contact.email.value")).toBe(true);
    expect(isValidFieldPath("skills[0].canonical_name")).toBe(true);
    expect(isValidFieldPath("experience[12].job_title.value")).toBe(true);
  });

  it("rejects malformed or injected paths", () => {
    expect(isValidFieldPath("")).toBe(false);
    expect(isValidFieldPath("; DROP TABLE candidates; --")).toBe(false);
    expect(isValidFieldPath("skills[0]..canonical_name")).toBe(false);
    expect(isValidFieldPath("0skills")).toBe(false);
  });
});

describe("scoredFieldPath", () => {
  it("appends .value to a base path", () => {
    expect(scoredFieldPath("contact.email")).toBe("contact.email.value");
  });
});
