import { test, expect } from "@playwright/test";

const image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a/p8AAAAASUVORK5CYII=";

test("send, upload, generated images, history reload, retry, and mobile layout", async ({ page }) => {
  const history: Record<number, unknown[]> = {};
  let nextId = 0;
  let fail = false;
  let sends = 0;
  const bodies: { role: string; content: unknown }[] = [];
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const id = Number(url.searchParams.get("conv_id"));
    if (url.pathname === "/api/conversations") {
      await route.fulfill({ json: Object.keys(history).map((id) => ({ conv_id: Number(id), title: `Chat ${id}` })) });
    } else if (url.pathname === "/api/create_conversation") {
      history[++nextId] = [];
      await route.fulfill({ json: { conv_id: nextId } });
    } else if (url.pathname === "/api/get_conversation") {
      await route.fulfill({ json: history[id] ?? [] });
    } else if (url.pathname === "/api/send_chat") {
      sends++;
      const body = route.request().postDataJSON();
      bodies.push(body);
      if (fail) {
        fail = false;
        await route.fulfill({ status: 502, json: { detail: "The model request failed." } });
      } else {
        const message = { role: "assistant", content: "Received your message.", images: [{ type: "image_url", image_url: { url: image } }] };
        history[id].push(body, message);
        await route.fulfill({ json: { choices: [{ message }] } });
      }
    }
  });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("button", { name: "New chat", exact: true }).click();
  const input = page.getByRole("textbox", { name: "Message", exact: true });
  const send = page.getByRole("button", { name: "Send", exact: true });
  await expect(send).toBeDisabled();
  await input.fill("Hello");
  await input.press("Enter");
  await expect(page.getByText("Received your message.", { exact: true })).toBeVisible();
  expect(bodies[0]).toEqual({ role: "user", content: "Hello" });
  await expect(page.getByAltText("Chat image")).toHaveCount(1);
  await expect(page.getByAltText("Chat image")).toHaveJSProperty("naturalWidth", 1);

  async function attachImage() {
    const chooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Attach image" }).click();
    const chooser = await chooserPromise;
    await chooser.setFiles({ name: "pixel.png", mimeType: "image/png", buffer: Buffer.from(image.split(",")[1], "base64") });
  }
  await attachImage();
  await expect(page.getByAltText("Attachment preview")).toBeVisible();
  await page.getByRole("button", { name: "Remove image" }).click();
  await expect(page.getByAltText("Attachment preview")).toHaveCount(0);
  await attachImage();
  await send.click();
  await expect(page.getByText("Received your message.", { exact: true })).toHaveCount(2);
  expect(bodies[1].content).toEqual([{ type: "image_url", image_url: { url: image } }]);
  await expect(page.getByAltText("Chat image")).toHaveCount(3);

  await page.reload();
  await expect(page.getByText("Received your message.", { exact: true })).toHaveCount(2);
  await expect(page.getByAltText("Chat image")).toHaveCount(3);
  fail = true;
  await input.fill("Retry me");
  await send.click();
  await expect(page.getByRole("alert")).toContainText("The model request failed.");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByText("Received your message.", { exact: true })).toHaveCount(3);
  await expect(page.getByText("Retry me", { exact: true })).toHaveCount(1);
  expect(sends).toBe(4);

  await page.getByRole("button", { name: "New chat", exact: true }).click();
  await expect(page.getByText("Send a message to start this chat.")).toBeVisible();
  await page.getByRole("button", { name: "Chat 1", exact: true }).click();
  await expect(page.getByText("Received your message.", { exact: true })).toHaveCount(3);
  await page.screenshot({ path: "test-results/chat-desktop.png" });
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(input).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/chat-mobile.png" });
  expect(errors).toEqual([]);
});

test("history failure can be retried without showing the wrong conversation", async ({ page }) => {
  let fail = true;
  await page.route("**/api/conversations", (route) => route.fulfill({ json: [{ conv_id: 1, title: "Saved chat" }] }));
  await page.route("**/api/get_conversation?conv_id=1", async (route) => {
    if (fail) { fail = false; await route.fulfill({ status: 500, json: { detail: "History unavailable" } }); }
    else await route.fulfill({ json: [{ role: "user", content: "Saved message" }] });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Saved chat" }).click();
  await expect(page.getByRole("alert")).toContainText("History unavailable");
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Retry loading" }).click();
  await expect(page.getByText("Saved message", { exact: true })).toBeVisible();
});
