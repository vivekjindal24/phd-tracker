// Images the API takes inline (specimen signatures, scholar photos): PNG or JPEG up to 500 KB.

const MAX_BYTES = 500_000; // the API's cap
const MAX_WIDTH = 800;

/** A phone photo is often past the cap: redraw it smaller, as JPEG on white. */
export async function shrink(file: File): Promise<Blob> {
  if (file.size <= MAX_BYTES) return file;
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_WIDTH / bitmap.width);
  const canvas = Object.assign(document.createElement("canvas"), {
    width: Math.round(bitmap.width * scale),
    height: Math.round(bitmap.height * scale),
  });
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("This browser cannot resize the image. Choose one under 500 KB.");
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("The image could not be resized."))), "image/jpeg", 0.85),
  );
}
