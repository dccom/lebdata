# Lebanon NH Assessment Data Visualization

This project downloads and visualizes property assessment data for Lebanon, NH.

## For Non-Programmers: Running with Docker Desktop

### Prerequisites
1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. Download this entire `vgsi` folder

### Steps to Run

1. **Open Terminal/Command Prompt**
   - **Mac**: Open Terminal (press Cmd+Space, type "Terminal")
   - **Windows**: Open Command Prompt or PowerShell

2. **Navigate to the vgsi folder**
   ```bash
   cd path/to/vgsi
   ```
   (Replace `path/to/vgsi` with the actual path to the folder)

3. **Start the server**
   ```bash
   docker-compose up
   ```

4. **Open your browser**
   - Go to: http://localhost:5050
   - You should see an interactive map with property data

5. **To stop the server**
   - Press `Ctrl+C` in the terminal
   - Or run: `docker-compose down`

### Troubleshooting

- **Port 5050 already in use**: Change the port in `docker-compose.yml` from `5050:5000` to `8080:5000`, then visit http://localhost:8080
- **Docker not found**: Make sure Docker Desktop is installed and running
- **Loading takes too long**: The first time, it geocodes all addresses which can take a while. Subsequent loads will be faster.

## Project Structure

- `scripts/` - Python scripts for downloading and processing data
- `lebdata/` - Flask web application for visualization
- `workspace/` - Downloaded data and CSV files
- `.devcontainer/` - VS Code development container configuration

## For Developers

See individual README files in subdirectories for more details on each component.
