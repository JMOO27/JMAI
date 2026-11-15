import type { AttachmentAdapter } from "@assistant-ui/react";

export const createImageAttachments = (onError: (message: string) => void): AttachmentAdapter => ({
  accept: "image/png,image/jpeg,image/webp,image/gif",
  async add({ file }) {
    if (!["image/png", "image/jpeg", "image/webp", "image/gif"].includes(file.type)) {
      const message = "Choose a PNG, JPEG, WebP, or GIF image.";
      onError(message);
      throw new Error(message);
    }
    if (file.size > 10 * 1024 * 1024) {
      const message = "Images must be 10 MB or smaller.";
      onError(message);
      throw new Error(message);
    }
    return {
      id: crypto.randomUUID(), type: "image", name: file.name, contentType: file.type, file,
      status: { type: "requires-action", reason: "composer-send" },
    };
  },
  async send(attachment) {
    if (!attachment.file) throw new Error("Please attach the image again.");
    const image = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = () => {
        const message = "Could not read the image. Please attach it again.";
        onError(message);
        reject(new Error(message));
      };
      reader.readAsDataURL(attachment.file!);
    });
    return { ...attachment, status: { type: "complete" }, content: [{ type: "image", image }] };
  },
  async remove() {},
});
