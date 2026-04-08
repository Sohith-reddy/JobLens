const API_BASE_URL = import.meta.env.FASTAPI_BACKEND_URL

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || ""
  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text()

  if (!response.ok) {
    const detail =
      typeof data === "object" && data !== null
        ? data.detail || data.message || JSON.stringify(data)
        : String(data)
    throw new Error(detail || `Request failed with status ${response.status}`)
  }

  return data
}

export async function scoreJobText(text) {
  const response = await fetch(`${API_BASE_URL}/scoring/text`, {
    method: "POST",
    headers: {
      "Content-Type": "text/plain",
    },
    body: text,
  })

  return parseResponse(response)
}

export async function scoreJobUrl(url) {
  const response = await fetch(`${API_BASE_URL}/scoring/url`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url }),
  })

  return parseResponse(response)
}

export async function matchResume({ resumeFile, jobDescription, useLlm = true, forceReparse = false }) {
  const formData = new FormData()
  formData.append("resume", resumeFile)
  formData.append("job_description", jobDescription)
  formData.append("use_llm", String(useLlm))
  formData.append("force_reparse", String(forceReparse))

  const response = await fetch(`${API_BASE_URL}/resume/match`, {
    method: "POST",
    body: formData,
  })

  return parseResponse(response)
}

export async function getSystemHealth() {
  const response = await fetch(`${API_BASE_URL}/health`)
  return parseResponse(response)
}

export async function getDetectionRules() {
  const response = await fetch(`${API_BASE_URL}/rules`)
  return parseResponse(response)
}

export { API_BASE_URL }
