# signal-generation-with-numpy — the *upstream* side

Generate IQ files in numpy for transmit via the safety-gated
`transmit_iq` MCP call. AM, FM, OOK, 2FSK, BPSK, QPSK, Manchester-encoded
OOK, simplified LoRa CSS. Every recipe is one function; every function
outputs a `.cs8` file that HackRF eats natively.
