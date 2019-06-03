# -*- coding: utf-8 -*-
"""
filename: UserPersonalAgent
Agent que implementa la interacció amb l'usuari
@author: ecsdi
"""
import random

import sys

import argparse
import socket
from multiprocessing import Process
from flask import Flask, render_template, request
from rdflib import Graph, Namespace, RDF, URIRef, Literal, XSD

from PlanificadorViajes.AgentUtil.ACLMessages import Agent,get_agent_info, build_message, send_message
from PlanificadorViajes.AgentUtil.FlaskServer import shutdown_server
from PlanificadorViajes.AgentUtil.Logging import config_logger
from PlanificadorViajes.AgentUtil.OntologyNamespaces import ACL
from PlanificadorViajes.AgentUtil.OntologyNamespaces import Ontologia

def get_count():
    return 1

if __name__ == '__main__':
    contentResult = Ontologia['Peticion_Planificar' + str(get_count())]
    gr = Graph()
    gr.add((contentResult, RDF.type, Ontologia.Peticion_Planificar))

    FormularioPlanCliente = Ontologia.FormularioPlanCliente
    gr.add((FormularioPlanCliente, Ontologia.tematica, Literal("tematica")))
    gr.add((FormularioPlanCliente, Ontologia.ciudad_destino, Literal("ciudad_destino")))
    gr.add((FormularioPlanCliente, Ontologia.ciudad_origen, Literal("ciudad_origen")))
    gr.add((FormularioPlanCliente, Ontologia.precio_max, Literal("precio_max")))
    gr.add((FormularioPlanCliente, Ontologia.precio_min, Literal("precio_min")))
    gr.add((FormularioPlanCliente, Ontologia.beginning, Literal("beginning")))
    gr.add((FormularioPlanCliente, Ontologia.end, Literal("end")))
    
    for s, p, o in gr:
        print (s, p, o)

    # #EJECUCION DEL MENSAJE
    # Planificador = get_agent_info(agn.AgentePlanificador, DirectoryAgent, UserClient, get_count())

    # gr1 = send_message(
    #     build_message(gr, perf=ACL.request, sender=UserClient.uri, receiver=Planificador.uri,
    #                     msgcnt=get_count(),
    #                     content=contentResult), Planificador.address)



