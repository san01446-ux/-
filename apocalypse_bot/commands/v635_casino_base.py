from __future__ import annotations

import discord
from discord.ext import commands

VERSION = "6.3.5a"


def register_v635_casino_base(bot: commands.Bot) -> None:
    patch_notes = bot.get_command("패치노트")
    if patch_notes is not None:
        async def v635_patch_notes(ctx: commands.Context) -> None:
            embed = discord.Embed(
                title="🎰🏕️ ABADDON v6.3.5a — 카지노·기지 + 던전 판정 핫픽스",
                description=(
                    "카지노 결과값과 기지 상태에 맞는 전용 이미지를 연결하고, "
                    "기지 성장을 장기 목표형 콘텐츠로 개편했습니다."
                ),
                color=discord.Color.dark_purple(),
            )
            embed.add_field(
                name="🎰 카지노 결과별 전용 연출",
                value=(
                    "• 슬롯: 일반 당첨·대승·잭팟·실패·치명 실패 분리\n"
                    "• 블랙잭·하이로우·바카라: 승리·대승·무승부·패배·버스트 분리\n"
                    "• 다이스·생존 룰렛·검은 주파수: 실제 손익과 위험도에 맞는 이미지 적용\n"
                    "• 결과 문구·배팅액·손익·리액션 이미지가 동일 판정값을 사용"
                ),
                inline=False,
            )
            embed.add_field(
                name="🏕️ 고난도 기지 업그레이드",
                value=(
                    "• Lv.1 야영지부터 Lv.5 요새급 기지까지 단계별 외형 적용\n"
                    "• 상위 단계일수록 나무·광석·고철·식량 요구량 대폭 증가\n"
                    "• 강화 즉시 완료 방식 제거: 30분·2시간·8시간·24시간 공사 시간 적용\n"
                    "• 건설·진행 중·성공·자원 부족·수확 결과별 전용 이미지 적용"
                ),
                inline=False,
            )
            embed.add_field(
                name="⚔️ 던전 전투력 판정 핫픽스",
                value=(
                    "• 전투력이 적의 2배 이상이면 확정 승리\n"
                    "• 우세 전투력에서도 발생하던 고정 20% 패배 구간 제거\n"
                    "• 골절·중독·감염 패널티가 전투력 우세를 과도하게 무효화하지 않도록 제한\n"
                    "• 전투 시작 메시지에 최종 승리 확률 표시"
                ),
                inline=False,
            )
            embed.add_field(
                name="📚 안내 최신화",
                value=(
                    "• `!명령어` 카지노/기지 카테고리 최신 명령어와 사용법 반영\n"
                    "• 공식 홈페이지 메인·업데이트 기록·명령어 검색을 v6.3.5로 동기화\n"
                    "• 장비·보물·펫·생활 콘텐츠와 기존 확률·전투 규칙은 유지"
                ),
                inline=False,
            )
            embed.set_footer(text="최신 버전 v6.3.5a · 던전 판정 긴급 수정")
            await ctx.send(embed=embed)

        patch_notes.callback = v635_patch_notes
        patch_notes.help = "ABADDON v6.3.5a 카지노·기지 및 던전 판정 핫픽스를 확인합니다."
        patch_notes.description = patch_notes.help

    bot.v635_casino_base_version = VERSION
