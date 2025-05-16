FROM coturn/coturn:latest
COPY turnserver.conf /etc/turnserver.conf
EXPOSE 3478/tcp 3478/udp
CMD ["turnserver", "-c", "/etc/turnserver.conf"]
