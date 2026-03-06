import { notFound } from "next/navigation";
import { DigestView } from "@/components/content/DigestView";
import { summariesServer } from "@/lib/api-server";

export default async function DailyPage({ params }: { params: Promise<{ date: string }> }) {
  const { date } = await params;

  let data;
  try {
    data = await summariesServer.daily(date);
  } catch {
    notFound();
  }

  const [year, month, day] = date.split("-");
  const title = `${year}년 ${month}월 ${day}일`;

  return (
    <DigestView
      title={title}
      subtitle="일간 다이제스트"
      content={data.content_md ?? "요약이 아직 생성되지 않았습니다."}
    />
  );
}
