"""
Defines the `SummationMPNN` class.
"""
# load general packages and functions
from collections import namedtuple
import torch


class SummationMPNN(torch.nn.Module):
    """
    Abstract `SummationMPNN` class. Specific models using this class are
    defined in `mpnn.py`; these are MNN, S2V, and GGNN.
    """
    def __init__(self, constants : namedtuple):

        super().__init__()

        self.hidden_node_features = constants.hidden_node_features
        self.edge_features        = constants.n_edge_features
        self.message_size         = constants.message_size
        self.message_passes       = constants.message_passes
        self.constants            = constants

    def message_terms(self, nodes : torch.Tensor, node_neighbours : torch.Tensor,
                      edges : torch.Tensor) -> None:
        """
        Message passing function, to be implemented in all `SummationMPNN` subclasses.

        Args:
        ----
            nodes (torch.Tensor)           : Batch of node feature vectors.
            node_neighbours (torch.Tensor) : Batch of node feature vectors for neighbors.
            edges (torch.Tensor)           : Batch of edge feature vectors.

        Shapes:
        ------
            nodes           : (total N nodes in batch, N node features)
            node_neighbours : (total N nodes in batch, max node degree, N node features)
            edges           : (total N nodes in batch, max node degree, N edge features)
        """
        raise NotImplementedError

    def update(self, nodes : torch.Tensor, messages : torch.Tensor) -> None:
        """
        Message update function, to be implemented in all `SummationMPNN` subclasses.

        Args:
        ----
            nodes (torch.Tensor)    : Batch of node feature vectors.
            messages (torch.Tensor) : Batch of incoming messages.

        Shapes:
        ------
            nodes    : (total N nodes in batch, N node features)
            messages : (total N nodes in batch, N node features)
        """
        raise NotImplementedError

    def readout(self, hidden_nodes : torch.Tensor, input_nodes : torch.Tensor,
                node_mask : torch.Tensor) -> None:
        """
        Local readout function, to be implemented in all `SummationMPNN` subclasses.

        Args:
        ----
            hidden_nodes (torch.Tensor) : Batch of node feature vectors.
            input_nodes (torch.Tensor) : Batch of node feature vectors.
            node_mask (torch.Tensor) : Mask for non-existing neighbors, where elements
                                       are 1 if corresponding element exists and 0
                                       otherwise.

        Shapes:
        ------
            hidden_nodes : (total N nodes in batch, N node features)
            input_nodes : (total N nodes in batch, N node features)
            node_mask : (total N nodes in batch, N features)
        """
        raise NotImplementedError

    def forward(self, nodes: torch.Tensor, edges: torch.Tensor) -> torch.Tensor:
        """
        Defines the forward pass, utilizing a structured approach to manage tensor shapes
        and operations efficiently, inspired by the `SummationMPNN` class.
    
        Args:
        ----
            nodes (torch.Tensor): Batch of node feature matrices.
            edges (torch.Tensor): Batch of edge feature tensors.
    
        Shapes:
        ------
            nodes: (batch size, N nodes, N node features)
            edges: (batch size, N nodes, N nodes, N edge features)
    
        Returns:
        -------
            output (torch.Tensor): Learned graph representation used to predict
                                   the action probability distribution for a batch of graphs.
        """
        adjacency = torch.sum(edges, dim=3)

        # Determine indices for nodes and their neighbors
        edge_batch_batch_idc, edge_batch_node_idc, edge_batch_nghb_idc = adjacency.nonzero(as_tuple=True)
        node_batch_batch_idc, node_batch_node_idc = adjacency.sum(-1).nonzero(as_tuple=True)

        node_batch_size = node_batch_batch_idc.shape[0]
        node_degrees = adjacency.sum(dim=-1).view(-1).long()
        max_node_degree = node_degrees.max()

        # Initialize tensors for node neighbors and edge features
        node_batch_node_nghbs = torch.zeros(node_batch_size, max_node_degree, self.hidden_node_features, device=nodes.device)
        node_batch_edges = torch.zeros(node_batch_size, max_node_degree, self.edge_features, device=nodes.device)
        node_batch_node_nghb_mask = torch.zeros(node_batch_size, max_node_degree, device=nodes.device)

        # Map edges to the corresponding nodes in the batch
        for i in range(node_batch_size):
            node_id = node_batch_node_idc[i]
            batch_id = node_batch_batch_idc[i]
            neighbors_idc = edge_batch_nghb_idc[(edge_batch_batch_idc == batch_id) & (edge_batch_node_idc == node_id)]
            for j, nghb_id in enumerate(neighbors_idc):
                node_batch_node_nghbs[i, j, :] = nodes[batch_id, nghb_id, :]
                node_batch_edges[i, j, :] = edges[batch_id, node_id, nghb_id, :]
                node_batch_node_nghb_mask[i, j] = 1

        # Pad up the hidden nodes to match batch and node dimensions
        hidden_nodes = torch.zeros_like(nodes, device=nodes.device)
        hidden_nodes[:, :nodes.shape[1], :] = nodes

        for _ in range(self.message_passes):
            messages = self.aggregate_message(nodes=hidden_nodes[node_batch_batch_idc, node_batch_node_idc, :],
                                              node_neighbours=node_batch_node_nghbs,
                                              edges=node_batch_edges,
                                              mask=node_batch_node_nghb_mask)
            hidden_nodes[node_batch_batch_idc, node_batch_node_idc, :] = self.update(hidden_nodes[node_batch_batch_idc, node_batch_node_idc, :], messages)

        node_mask = (adjacency.sum(-1) != 0)

        output = self.readout(hidden_nodes, nodes, node_mask)

        return output
