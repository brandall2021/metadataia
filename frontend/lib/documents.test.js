const assert = require("node:assert/strict");
const test = require("node:test");

const {
  documentCanRequestDeposit,
  documentCanRequestExtraction,
  documentCanRequestNormalization,
  documentCanRequestOcr,
  documentHasText,
  documentStatusMeta,
} = require("./documents.js");

test("documentStatusMeta devuelve copy legible para un estado conocido", () => {
  const meta = documentStatusMeta("OCR_COMPLETED");

  assert.equal(meta.label, "OCR listo");
  assert.equal(meta.tone, "cyan");
  assert.equal(meta.description, "El PDF ya tiene texto buscable");
});

test("documentCanRequestOcr solo habilita OCR cuando falta texto", () => {
  const detail = { needs_ocr: true, status: "UPLOADED", pages: [{ text: "" }] };

  assert.equal(documentHasText(detail), false);
  assert.equal(documentCanRequestOcr(detail), true);
  assert.equal(documentCanRequestExtraction(detail), false);
});

test("documentCanRequestExtraction exige texto y no necesita OCR", () => {
  const detail = { needs_ocr: false, status: "OCR_COMPLETED", pages: [{ text: "hola" }] };

  assert.equal(documentHasText(detail), true);
  assert.equal(documentCanRequestExtraction(detail), true);
});

test("documentCanRequestNormalization y deposit dependen de estado y registros", () => {
  const detail = {
    document_status: "APPROVED",
    records: [{ id: 1 }],
  };

  assert.equal(documentCanRequestNormalization(detail), true);
  assert.equal(documentCanRequestDeposit(detail), true);
});
