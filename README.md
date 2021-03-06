# networks
Assignment Specifications
You will implement the following five P2P services:
1. Data insertion: An external entity can request any peer to store a new data record into the
distributed database implemented as the DHT.
2. Data retrieval: An external entity can request any peer to retrieve a data record from the
DHT.
3. Peer joining: A new peer can approach any of the existing peers to join the DHT.
4. Peer departure (graceful): A peer can gracefully leave the DHT by announcing its
departure to other relevant peers before shutting down.
5. Peer departure (abrupt): Peers can depart abruptly, e.g., by “killing” a peer process using
CTRL-C command. 
For insertion, retrieval, or joining services, you are required to display the route taken along the
circular DHT to complete the service. The route is simply defined as the sequence of peers traversed
from the originating peer to the final one.
Following guidelines apply for implementing these services:
• A peer is implemented as a process and represented as an xterm, which can be used as an
interface to approach the peer. The xterm can also be used for the peer to display any
internal messages.
• The DHT identity of a peer is drawn from the range [0,255]. This means that technically, the
DHT can support a maximum of 256 peers to join the network. For tractability, however,
actual testing will be conducted with a small number of peers.
• Data records are files stored in the same directory where the assignment codes are stored.
• Filenames are four-digit numbers such as 0000, 0159, 1890, etc. Filenames such as a912 and
32134 are invalid because the former contains a non-numeral character and the latter does
not consist of exactly 4 numerals
• Hash function used to produce the key is given as modulus(filename/256), which results in a
key space of [0,255] matching the DHT identity space. For example, the hash of file 2012 is
220.
• A file producing a hash of n is stored in the peer that is the closest successor of n in the
circular DHT.
