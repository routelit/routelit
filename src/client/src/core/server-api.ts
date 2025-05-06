export async function sendEvent(
  event: CustomEvent<UIEventPayload>,
  fragmentId?: string
): Promise<ActionsResponse> {
  if (event.detail.type === "navigate") {
    return await handleNavigate(event as CustomEvent<NavigateEventPayload>);
  }
  return await handleUIEvent(event, fragmentId);
}

interface UIEvent {
  componentId: string;
  type: string;
  data: Record<string, unknown>;
  formId?: string;
}

interface RequestBody {
  uiEvent: UIEvent;
  fragmentId?: string;
}

async function sendUIEvent(url: string, body: RequestBody, headers?: Record<string, string>): Promise<ActionsResponse> {
  const res = await fetch(url, {
    method: "POST",
    body: JSON.stringify(body),
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error("Failed to send server event");
  }
  return res.json();
}

async function handleUIEvent(event: CustomEvent<UIEventPayload>, fragmentId?: string) {
  const { id, type, formId, ...data } = event.detail;
  const url = new URL(window.location.href);
  const body: RequestBody = {
    uiEvent: {
      componentId: id,
      type,
      data,
      formId,
    },
    fragmentId,
  };
  return await sendUIEvent(url.toString(), body);
}

async function handleNavigate(event: CustomEvent<NavigateEventPayload>) {
  const { href, id, type, lastURL, ...data } = event.detail;
  const body: RequestBody = {
    uiEvent: {
      componentId: id,
      type,
      data: {
        ...data,
        href,
      },
    },
  };
  const headers: Record<string, string> = {};
  if (lastURL) {
    headers["X-Referer"] = lastURL;
  }
  const response = await sendUIEvent(href, body, headers);
  if (event.detail.replace) {
    window.history.replaceState(null, "", href);
  } else {
    window.history.pushState(null, "", href);
  }
  return response;
}
