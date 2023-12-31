const express = require('express');
const fs = require('fs');
const { exec } = require('child_process');
const path = require('path');
const cors = require('cors'); // Import CORS module

const app = express();

// Configure CORS
// For development, you might allow all origins. For production, specify your extension's origin.
app.use(cors());

app.use(express.json({ limit: '100mb' })); // Adjust limit based on expected audio file sizes

app.post('/combine-audio', async (req, res) => {
    try {
        const audioClips = req.body.audioClips; // Array of base64 encoded audio clips
        let tempFiles = [];

        // Decode and write each audio clip to a temporary file
        for (let i = 0; i < audioClips.length; i++) {
            const buffer = Buffer.from(audioClips[i], 'base64');
            const tempFilePath = path.join(__dirname, `tempAudio${i}.wav`);
            fs.writeFileSync(tempFilePath, buffer);
            tempFiles.push(tempFilePath);
        }

        // Combine audio files using FFmpeg
        const combinedFilePath = path.join(__dirname, 'combinedAudio.mp3');
        const ffmpegCommand = `ffmpeg -y ${tempFiles.map(file => `-i ${file}`).join(' ')} -filter_complex concat=n=${tempFiles.length}:v=0:a=1 -acodec libmp3lame ${combinedFilePath}`;
        exec(ffmpegCommand, (error, stdout, stderr) => {
            if (error) {
                console.error(`Error combining audio: ${error.message}`);
                return res.status(500).send('Error combining audio');
            }

            // Read the combined MP3 file and send it as a response
            const combinedAudio = fs.readFileSync(combinedFilePath);
            res.send(Buffer.from(combinedAudio).toString('base64'));

            // Cleanup: Delete temporary and combined files
            tempFiles.forEach(file => fs.unlinkSync(file));
            fs.unlinkSync(combinedFilePath);
        });
    } catch (error) {
        console.error(`Server error: ${error.message}`);
        res.status(500).send('Server error');
    }
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
