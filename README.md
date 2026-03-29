# OneTap Server

Backend server for the OneTap Android application. Handles authentication, data synchronization, and business logic.

## Features

- REST API for mobile app communication
- User authentication and session management
- Data sync between devices
- Dockerized deployment

## Tech Stack

- **Language:** Python
- **Framework:** Flask / FastAPI
- **Deployment:** Docker

## Getting Started

```bash
# Clone the repository
git clone https://github.com/EasWay/OneTap-Server.git

# Install dependencies
pip install -r requirements.txt

# Run the server
python server.py
```

## Docker

```bash
# Build the image
docker build -t onetap-server .

# Run the container
docker run -p 5000:5000 onetap-server
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /auth/login | User login |
| POST | /auth/register | User registration |
| GET | /api/data | Fetch user data |
| POST | /api/sync | Sync data from device |

## Related Projects

- [OneTap Android App](https://github.com/EasWay/OneTap-AS) -- The mobile client

## License

MIT

## Author

**Godfred Fokuo** -- [GitHub](https://github.com/EasWay)
