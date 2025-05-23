import discord
from discord.ext import commands
from discord import app_commands
import os
import time
from supabase import create_client
from pydub import AudioSegment

connections = {}

# NOTE: using PyCord instead of discord.py for voice recording
# https://guide.pycord.dev/voice/receiving: recording functionality taken from here
class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.meeting_name = ""
        self.portfolio_id = ""

    async def finished_callback(self, sink: discord.sinks.WaveSink, channel: discord.TextChannel, *args):
        # Save all user audio files and upload to Supabase
        audio_segments = []
        temp_files = []
        for user_id, audio in sink.audio_data.items():
            file_path = f"{self.meeting_name}_{user_id}_{int(time.time())}.wav"
            with open(file_path, "wb") as f:
                f.write(audio.file.read())
                audio.file.seek(0)
            temp_files.append(file_path)
            # Load audio with pydub so that the audio can be mixed/appended together
            audio_segment = AudioSegment.from_wav(file_path)
            audio_segments.append(audio_segment)

        # Mix all audio tracks together for one whole meeting
        if audio_segments:
            mixed = audio_segments[0]
            for seg in audio_segments[1:]:
                mixed = mixed.overlay(seg)
            mixed_file_path = f"{self.meeting_name}_MIXED_{int(time.time())}.wav"
            mixed.export(mixed_file_path, format="wav")
            await self.upload_to_supabase(channel, mixed_file_path)
            os.remove(mixed_file_path)

        # Clean up temp files
        for file_path in temp_files:
            os.remove(file_path)

        await channel.send(f"Finished recording audio for: {self.meeting_name}.")

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

    @app_commands.command(name="record_voice", description="Start recording audio in the voice channel.")
    async def record(self, interaction: discord.Interaction, meeting_name: str, portfolio_id: str):
        voice = interaction.user.voice
        self.meeting_name = meeting_name
        self.portfolio_id = portfolio_id

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

    @app_commands.command(name="stop_voice_record", description="Stop recording and save the file.")
    async def stop_record(self, interaction: discord.Interaction):
        if interaction.guild.id in connections:
            vc = connections[interaction.guild.id]
            vc.stop_recording()  
            del connections[interaction.guild.id]
            await interaction.response.send_message("Stopped recording and processing audio.")
        else:
            await interaction.response.send_message("Not recording in this server.", ephemeral=True)

    @app_commands.command(name="join_voice", description="Join a voice channel.")
    async def join_voice(self, interaction: discord.Interaction):
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            await channel.connect()
            await interaction.response.send_message(f"Joined {channel.name}!")
        else:
            await interaction.response.send_message("Join a voice channel first.", ephemeral=True)

    @app_commands.command(name="leave_voice", description="Leave the voice channel.")
    async def leave_voice(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client:
            await voice_client.disconnect()
            await interaction.response.send_message("Disconnected.")
        else:
            await interaction.response.send_message("Not in a voice channel.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Voice(bot))
