export async function sendEvent(
  event: CustomEvent<UIEventPayload>
): Promise<Action[]> {
  const { id, type, ...data } = event.detail;
  const url = new URL(window.location.href);
  const body = {
    ui_event: {
      component_id: id,
      type,
      data,
    },
  };
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
