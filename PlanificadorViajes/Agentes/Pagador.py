# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 15:58:13 2013

Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: javier
"""

from __future__ import print_function

import argparse
from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph, logger, RDF
from flask import Flask, request

from PracticaTienda.utils.ACLMessages import register_agent, get_message_properties, build_message
from PracticaTienda.utils.FlaskServer import shutdown_server
from PracticaTienda.utils.Agent import Agent
from PracticaTienda.utils.OntoNamespaces import ACL
from PracticaTienda.utils.OntologyNamespaces import ECSDI

__author__ = 'Amazon V2'

parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor est abierto al exterior o no", action='store_true',
                    default=False)
parser.add_argument('--port', type=int, help="Puerto de comunicacion del agente")
parser.add_argument('--dhost', default=socket.gethostname(), help="Host del agente de directorio")
parser.add_argument('--dport', type=int, help="Puerto de comunicacion del agente de directorio")
parser.add_argument('--host', default=socket.gethostname(), help="Host del agente")


args = parser.parse_args()

# Configuration stuff
if args.port is None:
    port = 9003
else:
    port = args.port

if args.open is None:
    hostname = '0.0.0.0'
else:
    hostname = args.host

if args.dport is None:
    dport = 9000
else:
    dport = args.dport

if args.dhost is None:
    dhostname = socket.gethostname()
else:
    dhostname = args.dhost


agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
messages_cnt = 0

# Datos del Agente


AgentePublicador = Agent('AgentePublicador',
                       agn.AgentePublicador,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))


# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__, template_folder='../templates')

def get_count():
    global messages_cnt
    messages_cnt += 1
    return messages_cnt

def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio
    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    gr = register_agent(AgentePublicador, DirectoryAgent, AgentePublicador.uri, get_count())
    return gr

@app.route("/comm")
def comunicacion():

    global dsgraph
    global mss_cnt
    gr = None
    logger.info('Peticion de info recibida')

    # Extraemos el mensaje que nos envian
    mensaje = request.args['content']
    gm = Graph()
    gm.parse(data=mensaje)

    msgdic = get_message_properties(gm)

    # Comprobacion del mensaje

    if msgdic is None:
        gr = build_message(Graph(), ACL['no_entendido'], sender=AgentePublicador.uri, msgcnt=get_count())
    else:
        performative = msgdic['performative']

        if performative != ACL.request:
            gr = build_message(Graph(), ACL['no_entendido'], sender=AgentePublicador.uri, msgcnt=get_count())

        else:
            content = msgdic['content']
            accion = gm.value(subject=content, predicate=RDF.type)

            # Aqui realizariamos lo que pide la accion

            if accion == ECSDI.Registrar_productos:
                gr = recordExternalProduct(gm)

    logger.info('Respondemos a la peticion')

    return gr.serialize(format='xml'), 200


    pass


@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"

def recordExternalProduct(gm):
    ontologyFile = open('../Datos/productos')

    g = Graph()
    g.parse(ontologyFile, format='turtle')

    # Aquí afegim el producte al graf
    producto = gm.subjects(RDF.type, ECSDI.Producto_externo)
    producto = producto.next()

    for s, p, o in gm:
        if s == producto:
            g.add((s, p, o))

    # Guardem el graf
    g.serialize(destination='../Datos/productos', format='turtle')
    return gm


def tidyup():
    """
    Acciones previas a parar el agente

    """
    pass


def agentbehavior1():
    """
    Un comportamiento del agente

    :return:
    """
    register_message()
    pass


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=())
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')


