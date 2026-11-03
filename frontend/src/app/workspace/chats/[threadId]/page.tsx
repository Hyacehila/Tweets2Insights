import { Workspace } from "@/components/workspace";
export default async function Page({ params }: { params: Promise<{ threadId: string }> }) { const { threadId } = await params; return <Workspace threadId={threadId} />; }
