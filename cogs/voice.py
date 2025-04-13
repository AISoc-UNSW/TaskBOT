import discord
from discord.ext import commands
from discord import app_commands
import os
import time
import tempfile
import asyncio
from supabase import create_client
import subprocess

connections = {}
ffmpeg_processes = {} 

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.meeting_name = ""
        self.portfolio_id = ""

    async def finished_callback(self, interaction: discord.Interaction, file_path: str):
        await self.upload_to_supabase(interaction, file_path)

        os.remove(file_path)

        await interaction.channel.send("Finished recording and uploaded the file.")

    async def upload_to_supabase(self, interaction, file_path):
        try:
            SUPABASE_URL = os.getenv("SUPABASE_URL")
            SUPABASE_KEY = os.getenv("SUPABASE_KEY")
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

            # 获取频道名称
            channel_name = interaction.channel.name
            # 格式化时间，更易读
            formatted_time = time.strftime("%Y%m%d_%H%M%S")
            # 新的文件命名格式
            file_name = f"{channel_name}_{formatted_time}.wav"
            meeting_id = f"meeting_{channel_name}_{formatted_time}"

            with open(file_path, "rb") as audio_file:
                raw_audio_data = audio_file.read()

            supabase.table("meeting_records").insert({
                "Meeting ID": meeting_id,
                "Meeting Date": time.strftime("%Y-%m-%d"),
                "Meeting Name": f"{channel_name}_{self.meeting_name}",  # 组合频道名和会议名
                "Raw Audio Data": raw_audio_data,
                "Auto Caption": "",
                "Summary": "",
                "Portfolio ID": self.portfolio_id
            }).execute()

            await interaction.followup.send(f"Recording uploaded as `{file_name}`")
        except Exception as e:
            await interaction.followup.send(f"Failed to upload recording: {e}")

    @app_commands.command(name="record_voice", description="Start recording audio in the voice channel.")
    async def record(self, interaction: discord.Interaction, meeting_name: str, portfolio_id: str):
        """Start recording voice in a VC using ffmpeg."""
        voice = interaction.user.voice
        self.meeting_name = meeting_name
        self.portfolio_id = portfolio_id

        if not voice:
            return await interaction.response.send_message("You're not in a VC!", ephemeral=True)

        vc = interaction.guild.voice_client
        connections[interaction.guild.id] = vc
        
        temp_wav_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        ffmpeg_process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-f", "s16le",  
            "-ar", "48000",  
            "-ac", "2",      
            "-i", "-",       
            temp_wav_file,   
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        ffmpeg_processes[interaction.guild.id] = (ffmpeg_process, temp_wav_file)

        # Respond to the interaction
        if not interaction.response.is_done():
            await interaction.response.send_message("Recording started. Use `/stop_voice_record` to stop.")
        else:
            await interaction.followup.send("Recording started. Use `/stop_voice_record` to stop.")

    @app_commands.command(name="stop_voice_record", description="Stop recording and save the file.")
    async def stop_record(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if interaction.guild.id in ffmpeg_processes:
            ffmpeg_process, temp_wav_file = ffmpeg_processes[interaction.guild.id]
            ffmpeg_process.stdin.close()
            await ffmpeg_process.wait()

            if interaction.guild.id in connections:
                vc = connections[interaction.guild.id]
                await vc.disconnect()
                del connections[interaction.guild.id] 

            del ffmpeg_processes[interaction.guild.id]

            await self.finished_callback(interaction, temp_wav_file)
        else:
            await interaction.followup.send("Not recording in this server.", ephemeral=True)

    @app_commands.command(name="join_voice", description="Join a voice channel.")
    async def join_voice(self, interaction: discord.Interaction):
        """Joins the voice channel the user is in."""
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            await channel.connect()
            await interaction.response.send_message(f"Joined {channel.name}!")
        else:
            await interaction.response.send_message("Join a voice channel first.", ephemeral=True)

    @app_commands.command(name="leave_voice", description="Leave the voice channel.")
    async def leave_voice(self, interaction: discord.Interaction):
        """Leaves the voice channel if connected."""
        voice_client = interaction.guild.voice_client
        if voice_client:
            await voice_client.disconnect()
            await interaction.response.send_message("Disconnected.")
        else:
            await interaction.response.send_message("Not in a voice channel.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Voice(bot))
