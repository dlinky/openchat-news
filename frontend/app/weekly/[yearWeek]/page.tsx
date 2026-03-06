import { notFound } from "next/navigation";
import { DigestView } from "@/components/content/DigestView";
import { summariesServer } from "@/lib/api-server";

export default async function WeeklyPage({ params }: { params: Promise<{ yearWeek: string }> }) {
  const { yearWeek } = await params;

  let data;
  try {
    data = await summariesServer.weekly(yearWeek);
  } catch {
    notFound();
  }

  const [year, weekPart] = yearWeek.split("-W");
  const week = parseInt(weekPart);
  const title = `${year}년 ${week}주차`;

  return (
    <DigestView
      title={title}
      subtitle={data.date_from && data.date_to ? `${data.date_from} ~ ${data.date_to}` : "주간 다이제스트"}
      content={data.content_md ?? "요약이 아직 생성되지 않았습니다."}
    />
  );
}
