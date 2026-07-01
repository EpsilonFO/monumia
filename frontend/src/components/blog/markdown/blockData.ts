/* eslint-disable @typescript-eslint/no-explicit-any */
/** Lit et parse le JSON structuré posé par le plugin sur l'élément hast. */
export function readData<T>(node: any): T[] {
  try {
    return JSON.parse((node?.properties?.data as string) ?? '[]') as T[];
  } catch {
    return [];
  }
}
