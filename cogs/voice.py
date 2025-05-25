import discord
from discord.ext import commands
from discord import app_commands
import os
import time
from supabase import create_client
from pydub import AudioSegment
import subprocess

connections = {}

# NOTE: using PyCord instead of discord.py for voice recording
# https://guide.pycord.dev/voice/receiving: recording functionality taken from here
# COGS loading: https://guide.pycord.dev/popular-topics/cogs#cog-rules
 
class Voice(commands.Cog):
    # aka, for cogs, can do something like:
    # voice = discord.SlashCommandGroup("voice", "Meeting based voice commands")
    # or, leave it as discord.command
    def __init__(self, bot):
        self.bot = bot
        self.meeting_name = ""
        self.portfolio_id = ""

    async def finished_callback(self, sink: discord.sinks.WaveSink, channel: discord.TextChannel, *args):
        segments = []
        mention_strs = []

        for user_id, audio in sink.audio_data.items():
            raw_path = f"{user_id}_raw.wav"
            fixed_path = f"{user_id}_fixed.wav"

            with open(raw_path, "wb") as f:
                f.write(audio.file.getbuffer())

            # Fix with ffmpeg for compatibility (as pydub did not work well with raw wav audio)
            subprocess.run(["ffmpeg", "-y", "-i", raw_path, fixed_path], check=True)
            seg = AudioSegment.from_wav(fixed_path)

            segments.append(seg)
            mention_strs.append(f"<@{user_id}>")
            
            os.remove(raw_path)
            os.remove(fixed_path)

        if not segments:
            await channel.send("No audio recorded.")
            return

        # Overlay all user segments -> this will automatically handle silence 
        combined = segments[0]
        for seg in segments[1:]:
            combined = combined.overlay(seg)

        combined_file_name = f"meeting_{self.meeting_name}_{self.portfolio_id}.wav"
        combined.export(combined_file_name, format="wav")
        # Upload to Supabase + send finished message
        await self.upload_to_supabase(channel, combined_file_name)
        await channel.send(f"Finished recording for the meeting: {self.meeting_name}")
        os.remove(combined_file_name)

    async def upload_to_supabase(self, channel, file_path):
        try:
            SUPABASE_URL = os.getenv("SUPABASE_URL")
            SUPABASE_KEY = os.getenv("SUPABASE_KEY")
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

            curr_time = time.time()
            file_name = os.path.basename(file_path)

            with open(file_path, "rb") as audio_file:
                raw_audio_data = audio_file.read()

            supabase.table("Meetings Records").insert({
                "Meeting ID": f"meeting_{curr_time}",
                "Meeting Date": time.strftime("%Y-%m-%d"),
                "Meeting Name": self.meeting_name,
                "Raw Audio Data": raw_audio_data,
                "Auto Caption": "",
                "Summary": "",
                "Portfolio ID": self.portfolio_id
            }).execute()

            await channel.send(f"Recording uploaded directly to the 'Meetings' table as `{file_name}`.")
        except Exception as e:
            await channel.send(f"Failed to upload recording: {e}")

    @discord.slash_command(name="record_meet", description="Start recording audio in the voice channel.")
    async def record(self, interaction: discord.Interaction, meeting_name: str):
        voice = interaction.user.voice
        channel = interaction.user.voice.channel
        self.meeting_name = meeting_name
        self.portfolio_id = channel.category # Gets the portfolio ID/category based on the channel that the voice meeting is under

        if not voice:
            return await interaction.response.send_message("You're not in a VC!", ephemeral=True)

        vc = await voice.channel.connect()
        connections[interaction.guild.id] = vc

        # Recording audio using WaveSink
        vc.start_recording(
            discord.sinks.WaveSink(),
            self.finished_callback, # callback -> saved audio when stop_recording is invoked
            interaction.channel
        )

        await interaction.response.send_message("Recording started. Use `/stop_voice_record` to stop.")

    @discord.slash_command(name="stop_record", description="Stop recording and save the meeting.")
    async def stop(self, interaction: discord.Interaction):
        if interaction.guild.id in connections: 
            vc = connections[interaction.guild.id]
            vc.stop_recording()  
            del connections[interaction.guild.id] 
            await interaction.response.send_message("Stopped recording and cleaned up.", ephemeral=True)
        else:
            await interaction.response.send_message("I am currently not recording here.", ephemeral=True)

    @discord.slash_command(name="join_meeting", description="Join a voice channel to record meeting.")
    async def join(self, interaction: discord.Interaction):
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            await channel.connect()
            await interaction.response.send_message(f"Joined {channel.name}!")
        else:
            await interaction.response.send_message("Join a voice channel first.", ephemeral=True)

    @discord.slash_command(name="leave_meeting", description="Leave the meeting.")
    async def leave(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client:
            await voice_client.disconnect()
            await interaction.response.send_message("Disconnected.")
        else:
            await interaction.response.send_message("Not in a voice channel.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Voice(bot))
