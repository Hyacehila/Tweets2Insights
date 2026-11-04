/** Import one post JSON document with optional matching local images. */
export async function importDatasetFiles(
  files: File[],
  uploadImage: (file: File) => Promise<string>,
): Promise<Record<string, unknown>[]> {
  const documents = files.filter((file) => file.name.toLowerCase().endsWith(".json"));
  if (documents.length !== 1) throw new Error("请选择一个 JSON 文件，可同时选择它引用的配图。");
  const records = JSON.parse(await documents[0].text());
  if (!Array.isArray(records) || records.some((row) => !row || typeof row !== "object" || Array.isArray(row)))
    throw new Error("请上传由帖子记录组成的 JSON 数组。");
  const images = new Map<string, File>();
  for (const file of files.filter((file) => file !== documents[0])) {
    if (images.has(file.name)) throw new Error("配图文件名重复，请重命名后再导入。");
    if (file.size > 16 * 1024 * 1024) throw new Error("每张图片不得超过 16 MiB。");
    images.set(file.name, file);
  }
  // Validate the whole document before uploading any image.
  for (const row of records) {
    const refs = row.media_refs ?? row.image_urls ?? [];
    if (!Array.isArray(refs) || refs.some((ref) => typeof ref !== "string"))
      throw new Error("media_refs 必须是图片引用字符串数组。");
  }
  const uploaded = new Map<string, string>();
  const result = [];
  for (const row of records) {
    const refs = row.media_refs ?? row.image_urls ?? [];
    const mapped: string[] = [];
    for (const ref of refs) {
      // Remote URLs and already registered assets must never be matched by basename.
      const local = !/^(?:https?:|data:|dataset-image:)/i.test(ref);
      const name = ref.replaceAll("\\", "/").split("/").at(-1) ?? "";
      const image = local ? images.get(name) : undefined;
      if (image) {
        if (!uploaded.has(name)) uploaded.set(name, await uploadImage(image));
        mapped.push(uploaded.get(name)!);
      } else mapped.push(ref);
    }
    const { image_urls: _legacyImages, ...record } = row;
    result.push({ ...record, media_refs: mapped });
  }
  return result;
}
