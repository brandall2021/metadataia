const DOCUMENT_STATUS_META = {
  UPLOADED: { label: "Subido", tone: "amber", description: "Cargado y listo para procesar" },
  PROCESSING: { label: "Procesando", tone: "blue", description: "OCR o extracción en curso" },
  OCR_COMPLETED: { label: "OCR listo", tone: "cyan", description: "El PDF ya tiene texto buscable" },
  METADATA_EXTRACTED: { label: "Metadatos extraídos", tone: "violet", description: "Hay metadatos generados por IA" },
  NORMALIZED: { label: "Normalizado", tone: "emerald", description: "Valores convertidos al formato esperado" },
  VALIDATED: { label: "Validado", tone: "green", description: "Pasó las validaciones" },
  APPROVED: { label: "Aprobado", tone: "primary", description: "Listo para depósito" },
  REJECTED: { label: "Rechazado", tone: "rose", description: "Requiere corrección humana" },
  DEPOSITED: { label: "Depositado", tone: "slate", description: "Enviado al repositorio destino" },
};

function documentStatusMeta(status) {
  return DOCUMENT_STATUS_META[status] ?? {
    label: status,
    tone: "slate",
    description: "Estado no reconocido",
  };
}

function documentHasText(detail) {
  return Array.isArray(detail?.pages) && detail.pages.some((page) => (page?.text || "").trim().length > 0);
}

function documentCanRequestOcr(detail) {
  return Boolean(detail?.needs_ocr) && detail?.status !== "PROCESSING";
}

function documentCanRequestExtraction(detail) {
  return !detail?.needs_ocr && documentHasText(detail) && detail?.status !== "PROCESSING";
}

function documentCanRequestNormalization(detail) {
  return Array.isArray(detail?.records) && detail.records.length > 0;
}

function documentCanRequestValidation(detail) {
  return Array.isArray(detail?.records) && detail.records.length > 0;
}

function documentCanRequestDeposit(detail) {
  return detail?.document_status === "APPROVED";
}

module.exports = {
  DOCUMENT_STATUS_META,
  documentStatusMeta,
  documentHasText,
  documentCanRequestOcr,
  documentCanRequestExtraction,
  documentCanRequestNormalization,
  documentCanRequestValidation,
  documentCanRequestDeposit,
};
