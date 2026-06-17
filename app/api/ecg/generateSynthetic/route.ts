import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const { samples = 500 } = await req.json();

    const ecg: number[] = [];
    for (let i = 0; i < samples; i++) {
      const t = i / samples;

      const pWave = 0.1 * Math.sin(2 * Math.PI * (t * 5));
      const qrs = Math.exp(-Math.pow((t * 10 - 5), 2)) * 1.5;
      const tWave = 0.2 * Math.sin(2 * Math.PI * (t * 2));

      const value = pWave + qrs + tWave;
      ecg.push(value);
    }

    return NextResponse.json({
      success: true,
      samples,
      ecg,
    });
  } catch (error) {
    return NextResponse.json(
      { success: false, error: "Invalid request" },
      { status: 400 }
    );
  }
}
