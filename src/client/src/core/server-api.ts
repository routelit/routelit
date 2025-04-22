export async function sendEvent(
  event: CustomEvent<UIEventPayload>,
  fragmentId?: string
): Promise<Action[]> {
  if (event.detail.type === "navigate") {
    return await handleNavigate(event as CustomEvent<NavigateEventPayload>);
  }
  return await handleUIEvent(event, fragmentId);
}

interface RequestBody {
  ui_event: {
    component_id: string;
    type: string;
    data: Record<string, unknown>;
  };
  fragment_id?: string;
}

async function sendUIEvent(url: string, body: RequestBody): Promise<Action[]> {
  const res = await fetch(url, {
    method: "POST",
    body: JSON.stringify(body),
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error("Failed to send server event");
  }
  return res.json();
}

async function handleUIEvent(event: CustomEvent<UIEventPayload>, fragmentId?: string) {
  const { id, type, ...data } = event.detail;
  const url = new URL(window.location.href);
  const body: RequestBody = {
    ui_event: {
      component_id: id,
      type,
      data,
    },
    fragment_id: fragmentId,
  };
  return await sendUIEvent(url.toString(), body);
}

async function handleNavigate(event: CustomEvent<NavigateEventPayload>) {
  const { href, id, type, ...data } = event.detail;
  const body: RequestBody = {
    ui_event: {
      component_id: id,
      type,
      data: {
        ...data,
        href,
      },
    },
  };
  const response = await sendUIEvent(href, body);
  if (event.detail.replace) {
    window.history.replaceState(null, "", href);
  } else {
    window.history.pushState(null, "", href);
  }
  return response;
}
